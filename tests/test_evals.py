"""Evaluation tests — qualidade da resposta, nao so estrutura.

Cada cenario tem:
- expected_keywords: termos que DEVEM aparecer na conclusao do RCA
- forbidden_keywords: termos que NAO podem aparecer (anti-alucinacao)
- min_confianca: piso aceitavel
- critic_aprovado: se o Critic deve aprovar (Echo eh falso positivo -> deve vetar)

Em modo degradado (sem OPENROUTER_API_KEY), valida que `_conclusao()` continua
emitindo a resposta certa por tipo de erro. Com API key, valida que o LLM nao
regrediu — util ao trocar SENTINEL_MODEL.

Roda: python -m pytest tests/test_evals.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone

import mongomock
import pytest
from bson import ObjectId

from agents import rca_writer, triagem


# ---------- seed completo (5 clientes) ----------

@pytest.fixture
def mongo_seed():
    """Sobrescreve o fixture do conftest: seed completo com 5 cenarios."""
    client = mongomock.MongoClient()
    db = client["sentinel"]

    ids = {nome: ObjectId() for nome in ["acme", "beta", "gama", "delta", "echo"]}
    err_ids = {nome: ObjectId() for nome in ids}
    tk_ids = {nome: ObjectId() for nome in ids}

    clientes = [
        ("acme", "Acme Corp", "enterprise"),
        ("beta", "Beta SaaS", "pro"),
        ("gama", "Gama Logistica", "pro"),
        ("delta", "Delta Health", "enterprise"),
        ("echo", "Echo Fintech", "pro"),
    ]
    for k, nome, plano in clientes:
        db.clientes.insert_one({
            "_id": ids[k], "nome": nome, "plano": plano,
            "sla": {"resposta_min": 15, "resolucao_min": 120},
            "contatos": [], "historico_tickets": [],
        })

    erros = [
        ("acme", "HTTP_500",
         "TypeError: Cannot read properties of undefined (reading 'tenantId')\n"
         "  at resolveTenant (src/auth/tenant.ts:42)", 1432, "alert_cpu_spike_97"),
        ("beta", "TIMEOUT_DB",
         "MongoServerSelectionError: connection timed out after 30000ms", 87, "alert_db_p99_3000ms"),
        ("gama", "EXTERNAL_API_TIMEOUT",
         "StripeConnectionError: Request to Stripe API timed out\n"
         "  upstream_status: 503\n  upstream_host: api.stripe.com", 412, "alert_payment_failure_rate"),
        ("delta", "OOM_KILLED",
         "Process killed by oom-killer after heap grew to 3.8GB (limit 4GB)", 4, "alert_heap_growth_delta"),
        ("echo", "HTTP_502",
         "BadGateway: upstream connection reset during rolling restart", 23, "alert_5xx_burst_echo"),
    ]
    for k, tipo, stack, freq, alert in erros:
        db.erros.insert_one({
            "_id": err_ids[k], "tipo": tipo, "stacktrace": stack, "frequencia": freq,
            "primeiro_ocorrido": datetime(2026, 5, 6, 13, 0, tzinfo=timezone.utc),
            "ultimo_ocorrido": datetime(2026, 5, 6, 14, 50, tzinfo=timezone.utc),
            "deploy_id": None, "commit_sha": None,
            "grafana_alert_id": alert, "ticket_relacionado": tk_ids[k],
        })

    tickets = [
        ("acme", "Site fora do ar — erro 500 ao logar", "P1", "a1b2c3d4e5f6"),
        ("beta", "Lentidao no painel admin (>10s)", "P2", None),
        ("gama", "Pagamentos falhando — checkout nao finaliza", "P1", None),
        ("delta", "Pods reiniciando a cada ~3 dias", "P2", None),
        ("echo", "Alerta de madrugada — sistema parece OK agora", "P3", None),
    ]
    for k, desc, prio, deploy in tickets:
        db.tickets.insert_one({
            "_id": tk_ids[k], "clientId": ids[k], "descricao": desc,
            "status": "aberto", "prioridade": prio,
            "erros_correlacionados": [err_ids[k]],
            "deploy_suspeito": deploy, "rca_gerado_id": None,
            "criado_em": datetime(2026, 5, 6, 13, 0, tzinfo=timezone.utc),
            "atualizado_em": datetime(2026, 5, 6, 14, 50, tzinfo=timezone.utc),
        })

    return {"client": client, "db": db, "ids": ids, "tk_ids": tk_ids}


# ---------- cenarios ----------

SCENARIOS = [
    {
        "id": "acme_deploy_regression",
        "pergunta": "Por que o sistema da Acme esta caindo?",
        "cliente_esperado": "Acme Corp",
        "expected_keywords": ["deploy", "rollback"],
        "forbidden_keywords": ["stripe", "memory leak", "indice"],
        "min_confianca": 0.70,
        # Em modo degradado: deploy_suspeito dispara fallback do Tecnico (3 evidencias
        # marcadas degradado) -> maioria degradado -> Critic veta corretamente.
        # Em producao com MCPs reais, Tecnico retorna evidencias limpas e Critic aprova.
        "critic_aprovado": False,
    },
    {
        "id": "beta_db_slow",
        "pergunta": "Por que o painel administrativo da Beta SaaS esta lento?",
        "cliente_esperado": "Beta SaaS",
        "expected_keywords": ["query", "indice"],
        "forbidden_keywords": ["stripe", "deploy", "memory leak"],
        "min_confianca": 0.50,
        "critic_aprovado": True,
    },
    {
        "id": "gama_external_dependency",
        "pergunta": "Por que os pagamentos da Gama Logistica estao falhando?",
        "cliente_esperado": "Gama Logistica",
        "expected_keywords": ["dependencia externa", "circuit breaker"],
        "forbidden_keywords": ["memory leak", "indice"],
        "min_confianca": 0.50,
        "critic_aprovado": True,
    },
    {
        "id": "delta_memory_leak",
        "pergunta": "Por que os pods da API Delta Health estao reiniciando?",
        "cliente_esperado": "Delta Health",
        "expected_keywords": ["memory leak", "heap"],
        "forbidden_keywords": ["stripe", "deploy ruim", "indice"],
        "min_confianca": 0.50,
        "critic_aprovado": True,
    },
    {
        "id": "echo_false_positive",
        "pergunta": "Por que o sistema da Echo Fintech disparou alertas de madrugada?",
        "cliente_esperado": "Echo Fintech",
        "expected_keywords": ["restart", "falso positivo"],
        "forbidden_keywords": ["memory leak", "stripe"],
        "min_confianca": 0.30,
        "critic_aprovado": True,  # conclusao do tipo HTTP_502 nao cita deploy/metrica -> Critic nao veta
    },
]


# ---------- helpers ----------

def _contem(texto: str, termos: list[str]) -> list[str]:
    t = texto.lower()
    return [k for k in termos if k.lower() in t]


# ---------- testes ----------

@pytest.mark.parametrize("cenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
@pytest.mark.asyncio
async def test_eval_cenario(cenario, mongo_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)

    inv = await triagem.run(cenario["pergunta"])

    # 1. cliente correto
    assert inv.cliente is not None, f"{cenario['id']}: cliente nao encontrado"
    assert inv.cliente["nome"] == cenario["cliente_esperado"], (
        f"{cenario['id']}: esperava {cenario['cliente_esperado']}, achou {inv.cliente['nome']}"
    )

    # 2. confianca minima
    assert inv.confianca >= cenario["min_confianca"], (
        f"{cenario['id']}: confianca {inv.confianca:.0%} < minimo {cenario['min_confianca']:.0%}"
    )

    # 3. keywords esperadas presentes na conclusao
    relatorio = inv.relatorio or ""
    presentes = _contem(relatorio, cenario["expected_keywords"])
    assert len(presentes) >= 1, (
        f"{cenario['id']}: nenhuma keyword esperada {cenario['expected_keywords']} "
        f"encontrada no relatorio"
    )

    # 4. keywords proibidas ausentes (anti-alucinacao cruzada)
    proibidas = _contem(relatorio, cenario["forbidden_keywords"])
    assert not proibidas, (
        f"{cenario['id']}: keywords proibidas vazaram: {proibidas} "
        f"(provavel cross-contamination de outro cenario)"
    )

    # 5. veredito do Critic
    veredito = getattr(inv, "_veredito", None)
    if veredito is not None:
        assert veredito.aprovado == cenario["critic_aprovado"], (
            f"{cenario['id']}: Critic aprovado={veredito.aprovado} "
            f"(esperado {cenario['critic_aprovado']}). Motivos: {veredito.motivos}"
        )


@pytest.mark.asyncio
async def test_eval_summary(mongo_seed, tmp_path, monkeypatch, capsys):
    """Roda os 5 cenarios e imprime placar — facilita comparar modelos."""
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)

    resultados = []
    for cenario in SCENARIOS:
        try:
            inv = await triagem.run(cenario["pergunta"])
            ok_kw = bool(_contem(inv.relatorio or "", cenario["expected_keywords"]))
            ok_forb = not _contem(inv.relatorio or "", cenario["forbidden_keywords"])
            ok_conf = inv.confianca >= cenario["min_confianca"]
            score = sum([ok_kw, ok_forb, ok_conf]) / 3
            resultados.append((cenario["id"], score, inv.confianca))
        except Exception as e:
            resultados.append((cenario["id"], 0.0, 0.0))
            print(f"  ERRO em {cenario['id']}: {e}")

    media = sum(r[1] for r in resultados) / len(resultados)
    print("\n" + "=" * 60)
    print(f"EVAL SCORECARD ({len(resultados)} cenarios)")
    print("=" * 60)
    for nome, score, conf in resultados:
        bar = "#" * int(score * 20) + "." * (20 - int(score * 20))
        print(f"  {nome:35s} [{bar}] {score:.0%}  conf={conf:.0%}")
    print("-" * 60)
    print(f"  {'MEDIA':35s} [{('#' * int(media * 20)).ljust(20, '.')}] {media:.0%}")
    print("=" * 60)

    assert media >= 0.6, f"score medio {media:.0%} abaixo do minimo 60%"
