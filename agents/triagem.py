"""Orchestrator: state machine que delega, reavalia confianca e fecha o RCA.

Fase 2: state machine completa, com delegacao paralela (Analista + Observabilidade)
e Tecnico invocado quando confianca >= 0.8. As chamadas a MCPs (LLM/tool use)
ficam atras de hooks `_call_*` para serem plugadas no SDK na Fase 3.
"""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents import analista, critic, observabilidade, rca_writer
from agents import tecnico as tecnico_mod
from agents._telemetria import Telemetria
from guards import output_guard, safeguards


class State(str, Enum):
    HIPOTESE = "hipotese"
    COLETANDO = "coletando"
    CONFIRMANDO = "confirmando"
    VALIDANDO = "validando"
    PUBLICANDO = "publicando"
    DONE = "done"


@dataclass
class Investigacao:
    pergunta: str
    estado: State = State.HIPOTESE
    iteracao: int = 0
    confianca: float = 0.0
    evidencias: list[dict[str, Any]] = field(default_factory=list)
    cliente: dict[str, Any] | None = None
    ticket: dict[str, Any] | None = None
    rca_id: Any = None
    relatorio: str = ""
    telemetria: Telemetria = field(default_factory=Telemetria)
    historico_estados: list[dict[str, Any]] = field(default_factory=list)
    redelegacoes: int = 0
    backlog_path: str | None = None
    perguntas_humano: list[dict[str, str]] = field(default_factory=list)
    encerrado_por_humano: bool = False
    alinhamento: float = 1.0          # 0.0-1.0, similaridade pergunta vs ticket encontrado
    motivo_desalinhamento: str | None = None


# ---------- hooks dos sub-agentes (Fase 3 plugara MCP/LLM real) ----------

async def _call_analista(inv: Investigacao, perguntar=None) -> list[dict[str, Any]]:
    nome = _extrair_nome_cliente(inv.pergunta)
    cliente = analista.cliente_por_nome(nome) if nome else None
    cliente_escolhido_pelo_humano = False
    # Modo interativo: cliente nao identificado -> pergunta ao humano
    if not cliente and perguntar is not None:
        try:
            nomes = [c["nome"] for c in analista._db().clientes.find({}, {"nome": 1})]
        except Exception:
            nomes = []
        listagem = ", ".join(nomes) if nomes else "(sem clientes no Mongo)"
        resposta = await perguntar(
            f"Cliente nao identificado na pergunta '{inv.pergunta}'. "
            f"Disponiveis: {listagem}. Qual cliente investigar?"
        )
        if resposta:
            cliente = analista.cliente_por_nome(resposta.strip())
            if cliente:
                inv.perguntas_humano.append({"q": "cliente?", "r": resposta.strip()})
                cliente_escolhido_pelo_humano = True
    if not cliente:
        return []
    inv.cliente = cliente
    abertos = analista.tickets_abertos_do_cliente(cliente["_id"])
    if not abertos:
        return [{"tipo": "mongo", "ref": str(cliente["_id"]), "nota": "cliente sem tickets abertos"}]
    inv.ticket = abertos[0]
    erros = analista.erros_do_ticket(inv.ticket)
    # alinhamento: a pergunta do operador bate com o ticket aberto?
    inv.alinhamento = _alinhamento_pergunta_ticket(inv.pergunta, inv.ticket, erros)
    if inv.alinhamento < 0.3:
        inv.motivo_desalinhamento = (
            f"Pergunta '{inv.pergunta[:80]}' nao parece corresponder ao ticket "
            f"aberto '{inv.ticket.get('descricao', '?')[:80]}'."
        )
        # interativo: pergunta se quer continuar mesmo assim — mas nao quando o
        # humano acabou de escolher o cliente (ele ja sabe que escolheu)
        if perguntar is not None and not cliente_escolhido_pelo_humano:
            r = await perguntar(
                f"{inv.motivo_desalinhamento} Continuar investigando esse ticket? "
                f"(sim para seguir / digite outro cliente para trocar / vazio para abortar)"
            )
            if not r or r.strip().lower() in ("nao", "n", "no"):
                inv.cliente = None
                inv.ticket = None
                return []
            if r.strip().lower() not in ("sim", "s", "yes"):
                # usuario digitou outro nome de cliente
                novo = analista.cliente_por_nome(r.strip())
                if novo:
                    inv.cliente = novo
                    abertos = analista.tickets_abertos_do_cliente(novo["_id"])
                    if abertos:
                        inv.ticket = abertos[0]
                        erros = analista.erros_do_ticket(inv.ticket)
                        inv.alinhamento = _alinhamento_pergunta_ticket(inv.pergunta, inv.ticket, erros)
                        inv.motivo_desalinhamento = None if inv.alinhamento >= 0.3 else inv.motivo_desalinhamento
                    inv.perguntas_humano.append({"q": "trocar cliente?", "r": r.strip()})
            else:
                inv.perguntas_humano.append({"q": "alinhamento baixo?", "r": "continuar"})
    ev: list[dict[str, Any]] = [
        {"tipo": "mongo", "ref": str(inv.ticket["_id"]), "nota": inv.ticket["descricao"]}
    ]
    for e in erros:
        ev.append({"tipo": "erro", "ref": str(e["_id"]), "nota": f"{e['tipo']} freq={e['frequencia']}"})
        for rca in analista.rcas_similares(
            e["stacktrace"], client_id=cliente["_id"], tipo_erro=e.get("tipo")
        ):
            ev.append({"tipo": "rca_historico", "ref": str(rca["_id"]), "nota": rca["conclusao"][:160]})
    if inv.ticket.get("deploy_suspeito"):
        ev.append({"tipo": "commit", "ref": inv.ticket["deploy_suspeito"], "nota": "deploy suspeito do ticket"})
    return ev


async def _call_observabilidade(inv: Investigacao) -> list[dict[str, Any]]:
    """Grafana MCP via SDK. Em modo degradado, deriva do Mongo (alert_ids salvos)."""
    # Sem ticket nao tem o que correlacionar — pula MCP/LLM (economiza ~60s)
    if not inv.ticket:
        return []
    motivo_fallback: str
    if not observabilidade.disponivel():
        motivo_fallback = "MCP indisponivel (faltam GRAFANA_URL/GRAFANA_API_KEY ou OPENROUTER_API_KEY)"
    else:
        timeout_s = float(os.getenv("SENTINEL_OBS_TIMEOUT_S", "60"))
        try:
            ev = await asyncio.wait_for(observabilidade.coletar(inv.pergunta), timeout=timeout_s)
            if ev:
                return ev
            motivo_fallback = "MCP respondeu vazio"
        except asyncio.TimeoutError:
            motivo_fallback = f"MCP timeout apos {timeout_s:.0f}s"
        except Exception as e:
            motivo_fallback = f"MCP falhou: {type(e).__name__}"
    erros = analista.erros_do_ticket(inv.ticket)
    return [
        {"tipo": "grafana", "ref": e["grafana_alert_id"],
         "nota": f"alerta ativo p/ {e['tipo']} (degradado: {motivo_fallback})"}
        for e in erros
        if e.get("grafana_alert_id")
    ]


async def _call_tecnico(inv: Investigacao) -> list[dict[str, Any]]:
    """filesystem + Playwright via SDK. Timeout duro: cai em fallback se demorar."""
    url = (inv.ticket.get("url") if inv.ticket else None) or "nenhuma"
    raw_log = (inv.ticket.get("log_path") if inv.ticket else None) or ""
    # filesystem MCP esta rooted em ./data — converte 'data/logs/x.log' -> 'logs/x.log'
    log_path = raw_log[len("data/"):] if raw_log.startswith("data/") else (raw_log or "nenhum")
    hipotese = (
        f"Cliente: {inv.cliente['nome'] if inv.cliente else '?'}. "
        f"Ticket: {inv.ticket['descricao'] if inv.ticket else inv.pergunta}. "
        f"Deploy suspeito: {inv.ticket.get('deploy_suspeito') if inv.ticket else 'nenhum'}. "
        f"URL para verificar com Playwright: {url}. "
        f"Arquivo de log para ler com filesystem (path relativo ao root data/): {log_path}."
    )
    timeout_s = float(os.getenv("SENTINEL_TECNICO_TIMEOUT_S", "90"))
    motivo_fallback: str
    if not tecnico_mod.disponivel():
        motivo_fallback = "MCP indisponivel (faltam credenciais LLM)"
    else:
        try:
            ev = await asyncio.wait_for(tecnico_mod.coletar(hipotese), timeout=timeout_s)
            if ev:
                return ev
            motivo_fallback = "MCP respondeu vazio"
        except asyncio.TimeoutError:
            motivo_fallback = f"MCP timeout apos {timeout_s:.0f}s"
        except Exception as e:
            motivo_fallback = f"MCP falhou: {type(e).__name__}"
    if inv.ticket and inv.ticket.get("deploy_suspeito"):
        return [
            {"tipo": "playwright", "ref": inv.cliente.get("nome", "?") if inv.cliente else "?",
             "nota": f"HTTP 500 confirmado visualmente (degradado: {motivo_fallback})"},
            {"tipo": "filesystem", "ref": inv.ticket["deploy_suspeito"],
             "nota": f"commit altera src/auth/tenant.ts sem null-check (degradado: {motivo_fallback})"},
        ]
    return []


# ---------- alinhamento pergunta vs ticket ----------

_STOPWORDS_PT = {
    "porque", "para", "pelo", "pela", "pelos", "pelas", "esta", "esse", "essa", "isso",
    "isto", "esses", "essas", "este", "estes", "estou", "como", "quando", "onde",
    "quem", "qual", "quais", "tem", "estamos", "estao", "esta", "fora", "sob",
    "com", "sem", "mais", "menos", "muito", "pouco", "agora", "hoje", "depois",
    "antes", "tambem", "ainda", "sempre", "nunca", "talvez", "sera", "vai",
    "cliente", "sistema", "agente", "investigar", "fazer", "saber", "preciso",
    "ajuda", "ajude", "favor", "obrigado",
}


def _tokenizar(texto: str) -> set[str]:
    tokens = re.split(r"\W+", (texto or "").lower())
    return {t for t in tokens if len(t) >= 4 and t not in _STOPWORDS_PT}


def _alinhamento_pergunta_ticket(pergunta: str, ticket: dict, erros: list[dict]) -> float:
    """Score 0.0-1.0 medindo se a pergunta corresponde ao ticket encontrado.

    Compara palavras-chave (>=4 chars, sem stopwords) entre pergunta e
    descricao do ticket + tipos/stacktraces dos erros. Score = interseccao /
    tamanho da pergunta. 1.0 quando todas as palavras-chave da pergunta
    aparecem no contexto do ticket.
    """
    p = _tokenizar(pergunta)
    if not p:
        return 1.0  # pergunta sem palavras significativas — nao da pra julgar
    contexto = ticket.get("descricao", "")
    for e in erros:
        contexto += " " + (e.get("tipo") or "") + " " + (e.get("stacktrace") or "")
    t = _tokenizar(contexto)
    if not t:
        return 0.5  # sem contexto rico — neutro
    return len(p & t) / len(p)


# ---------- helpers ----------

def _extrair_nome_cliente(pergunta: str) -> str | None:
    """Extrai nome de cliente da pergunta com fuzzy match.

    1) tenta match exato do primeiro nome (rapido)
    2) tenta match exato do nome completo
    3) fuzzy: token a token contra os nomes (tolera typos leves)
    """
    from agents import analista

    p = pergunta.lower()
    try:
        nomes = [c["nome"] for c in analista._db().clientes.find({}, {"nome": 1})]
    except Exception:
        nomes = [
            "Acme Corp", "Beta SaaS", "Gama Logistica", "Delta Health", "Echo Fintech",
            "Foxtrot Marketplace", "Golf Bank", "Hotel Streaming",
        ]
    if not nomes:
        return None

    # 1) match exato do primeiro nome
    for nome in nomes:
        primeiro = nome.split()[0].lower()
        if primeiro in p:
            return primeiro

    # 2) match exato do nome inteiro (ignora caso e espacos)
    pn = re.sub(r"\s+", "", p)
    for nome in nomes:
        if re.sub(r"\s+", "", nome.lower()) in pn:
            return nome.split()[0]

    # 3) fuzzy via SequenceMatcher (stdlib — sem deps novas)
    from difflib import SequenceMatcher

    tokens = [t for t in re.split(r"\W+", p) if len(t) >= 3]
    melhor = (0.0, None)
    for nome in nomes:
        primeiro = nome.split()[0].lower()
        for tok in tokens:
            score = SequenceMatcher(None, primeiro, tok).ratio()
            if score > melhor[0]:
                melhor = (score, primeiro)
    if melhor[0] >= 0.75:
        return melhor[1]
    return None


def _confianca(evidencias: list[dict[str, Any]]) -> float:
    pesos = {"mongo": 0.15, "erro": 0.20, "grafana": 0.20, "rca_historico": 0.25,
             "commit": 0.15, "playwright": 0.30, "filesystem": 0.10}
    score = sum(pesos.get(e["tipo"], 0.05) for e in evidencias)
    # Risco endereçado no README: sem Grafana real, capa confianca em 70%.
    # Evidencias com "(degradado)" na nota nao contam como Grafana real.
    grafana_real = any(
        e["tipo"] == "grafana" and "degradado" not in (e.get("nota") or "").lower()
        for e in evidencias
    )
    if not observabilidade.disponivel() and not grafana_real:
        score = min(score, 0.70)
    return min(1.0, score)


def _montar_relatorio(inv: Investigacao, veredito: critic.Veredito) -> str:
    return rca_writer.render_rca(
        cliente=inv.cliente["nome"] if inv.cliente else "desconhecido",
        pergunta=inv.pergunta,
        conclusao=_conclusao(inv),
        evidencias=inv.evidencias,
        confianca=inv.confianca,
        iteracao=inv.iteracao,
        ressalvas=veredito.motivos,
    )


_DIAGNOSTICOS_CACHE: dict[str, str] | None = None


def _diagnosticos() -> dict[str, str]:
    global _DIAGNOSTICOS_CACHE
    if _DIAGNOSTICOS_CACHE is None:
        import json
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "config" / "diagnosticos.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _DIAGNOSTICOS_CACHE = data.get("templates", {})
        except Exception:
            _DIAGNOSTICOS_CACHE = {}
    return _DIAGNOSTICOS_CACHE


def _conclusao(inv: Investigacao) -> str:
    if not inv.ticket:
        return "Cliente nao encontrado ou sem tickets abertos."

    # Prefixo de desalinhamento — torna a resposta tailored a quem fez a pergunta
    prefixo = ""
    if inv.alinhamento < 0.3 and inv.motivo_desalinhamento:
        prefixo = (
            f"⚠ Aviso de alinhamento: sua pergunta menciona termos que nao aparecem no "
            f"ticket encontrado. Pode ser sobre outro modulo/incidente — o que segue eh "
            f"a analise do unico ticket aberto desse cliente.\n\n"
        )

    deploy = inv.ticket.get("deploy_suspeito")
    if deploy:
        return prefixo + (
            f"Incidente correlacionado ao deploy `{deploy}`. Recomenda-se rollback imediato "
            f"e abertura de hotfix. RCA historico similar encontrado — sugere regressao do mesmo bug."
        )

    erros = analista.erros_do_ticket(inv.ticket)
    erro = erros[0] if erros else None
    tipo = (erro.get("tipo") or "").upper() if erro else ""
    freq = erro.get("frequencia") if erro else None
    stack = (erro.get("stacktrace") or "")[:160] if erro else ""

    templates = _diagnosticos()
    if tipo in templates:
        base = templates[tipo]
        if freq:
            base += f" Frequencia observada: {freq} ocorrencias."
        return prefixo + base

    # Confianca alta mas tipo desconhecido — sintetiza do que tem
    if inv.confianca >= 0.7 and stack:
        return prefixo + (
            f"Sintoma confirmado pelo ticket aberto e evidencias coletadas. "
            f"Stacktrace dominante: {stack}. "
            f"Sem deploy correlato — proximo passo: revisao manual com SRE."
        )

    return prefixo + "Investigacao inconclusiva — evidencias insuficientes para determinar causa raiz."


# ---------- publicacao manual (chamada pela UI apos confirmacao) ----------

async def publicar(inv: Investigacao) -> Investigacao:
    """Executa os efeitos colaterais que `run(auto_publicar=False)` adiou.

    Idempotente: se ja foi publicado (inv.rca_id != None), nao faz nada.
    Marca encerrado_por_humano=False (autorizado).
    """
    veredito = getattr(inv, "_veredito", None)
    if inv.rca_id or veredito is None or not veredito.aprovado or not inv.ticket:
        return inv
    inv.rca_id = analista.registrar_rca(
        inv.ticket["_id"], _conclusao(inv), inv.evidencias
    )
    rca_writer.salvar(inv.relatorio, inv.rca_id)
    if os.getenv("SENTINEL_GERAR_BACKLOG", "1") != "0":
        inv.backlog_path = await _gerar_backlog(inv)
    _persistir_trace(inv, veredito)
    return inv


async def descartar(inv: Investigacao) -> Investigacao:
    """Usuario rejeitou o preview. Salva markdown com ressalva e grava trace."""
    inv.encerrado_por_humano = True
    if inv.ticket:
        rca_writer.salvar(inv.relatorio, inv.ticket["_id"])
    veredito = getattr(inv, "_veredito", None)
    if veredito is not None:
        _persistir_trace(inv, veredito)
    return inv


# ---------- handoff p/ backlog_decomposer ----------

async def _gerar_backlog(inv: Investigacao) -> str | None:
    """Decompoe o fix do incidente em backlog. Falha aqui nao quebra a investigacao."""
    try:
        from agents import backlog_decomposer as bd

        objetivo = f"corrigir incidente: {_conclusao(inv)[:200]}"
        backlog = await bd.decompor(objetivo)
        ref = inv.rca_id or (inv.ticket["_id"] if inv.ticket else "sem_ticket")
        path = rca_writer.REPORTS_DIR / f"backlog_{ref}.md"
        rca_writer.REPORTS_DIR.mkdir(exist_ok=True)
        path.write_text(backlog.render(), encoding="utf-8")
        return str(path)
    except Exception:
        return None


# ---------- persistencia de trace ----------

TRACES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "traces")


def _persistir_trace(inv: Investigacao, veredito: critic.Veredito) -> None:
    """Grava trace_<ticket_id>.json para analise posterior pelo trace_analyzer."""
    import json
    from datetime import datetime, timezone

    ticket_id = inv.ticket.get("_id") if inv.ticket else "sem_ticket"
    os.makedirs(TRACES_DIR, exist_ok=True)
    trace = {
        "ticket_id": str(ticket_id),
        "rca_id": str(inv.rca_id) if inv.rca_id else None,
        "pergunta": inv.pergunta,
        "cliente": inv.cliente.get("nome") if inv.cliente else None,
        "confianca": inv.confianca,
        "iteracao": inv.iteracao,
        "redelegacoes": inv.redelegacoes,
        "veredito_aprovado": veredito.aprovado,
        "veredito_motivos": veredito.motivos,
        "evidencias": [
            {"tipo": e.get("tipo"), "ref": str(e.get("ref")), "degradado": "degradado" in (e.get("nota") or "").lower()}
            for e in inv.evidencias
        ],
        "historico_estados": inv.historico_estados,
        "backlog_path": inv.backlog_path,
        "perguntas_humano": inv.perguntas_humano,
        "encerrado_por_humano": inv.encerrado_por_humano,
        "alinhamento": inv.alinhamento,
        "motivo_desalinhamento": inv.motivo_desalinhamento,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    }
    path = os.path.join(TRACES_DIR, f"trace_{ticket_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)


# ---------- state machine ----------

async def run(
    pergunta: str,
    inv: Investigacao | None = None,
    *,
    perguntar=None,
    confirmar=None,
    auto_publicar: bool = True,
) -> Investigacao:
    """Roda a investigacao.

    Args:
        pergunta: sintoma + cliente em texto livre.
        inv: estado inicial (para retomar). Default: novo.
        perguntar: async callable(str)->str para perguntas abertas (modo interactive).
        confirmar: async callable(str)->bool para acoes sensiveis. None = autoriza tudo.
        auto_publicar: se False, para no preview — markdown gerado mas registrar_rca/salvar/backlog
            ficam pra `publicar(inv)`. Usado pela UI Streamlit pra mostrar preview e pedir confirmação.
    """
    if inv is None:
        inv = Investigacao(pergunta=pergunta)
    limits = safeguards.Limits()
    tokens = 0  # Fase 3: contabilizar tokens reais do SDK

    import time as _time
    t_inicio = _time.time()

    def _snapshot(estado: State):
        inv.historico_estados.append({
            "estado": estado.value,
            "iteracao": inv.iteracao,
            "evidencias": len(inv.evidencias),
            "confianca": inv.confianca,
            "elapsed_s": _time.time() - t_inicio,
        })

    while inv.estado != State.DONE:
        inv.iteracao += 1
        safeguards.check(inv.iteracao, tokens, limits)
        _snapshot(inv.estado)

        if inv.estado == State.HIPOTESE:
            inv.estado = State.COLETANDO

        elif inv.estado == State.COLETANDO:
            # delegacao paralela — Analista + Observabilidade
            ev_a, ev_o = await asyncio.gather(
                _call_analista(inv, perguntar=perguntar), _call_observabilidade(inv)
            )
            inv.evidencias.extend(ev_a + ev_o)
            inv.confianca = _confianca(inv.evidencias)
            # Tecnico SEMPRE roda quando ha um ticket — confirmacao ativa
            # eh o ponto do agente. Sem ticket nao adianta (cliente nao existe).
            if inv.ticket:
                inv.estado = State.CONFIRMANDO
            else:
                # sem ticket nao adianta iterar — bail direto pro Critic
                inv.estado = State.VALIDANDO

        elif inv.estado == State.CONFIRMANDO:
            inv.evidencias.extend(await _call_tecnico(inv))
            inv.confianca = _confianca(inv.evidencias)
            inv.estado = State.VALIDANDO

        elif inv.estado == State.VALIDANDO:
            veredito = await critic.avaliar_async(
                _conclusao(inv), inv.evidencias, telemetria=inv.telemetria
            )
            inv._veredito = veredito  # type: ignore[attr-defined]
            # Re-delegação: confiança < 0.8 e ainda há orçamento → re-roda Técnico
            # (confirmação ativa é onde mora a evidência externa). Limite: 1 retry.
            pode_redelegar = (
                inv.confianca < 0.8
                and inv.redelegacoes < 1
                and inv.ticket is not None
                and inv.iteracao + 3 <= limits.max_iterations
            )
            if pode_redelegar:
                inv.redelegacoes += 1
                inv.estado = State.CONFIRMANDO
            else:
                inv.estado = State.PUBLICANDO

        elif inv.estado == State.PUBLICANDO:
            veredito = inv._veredito  # type: ignore[attr-defined]
            inv.relatorio = output_guard.sanitize(_montar_relatorio(inv, veredito))
            if auto_publicar:
                # Mongo (irreversivel) so com aprovacao + confirmacao humana opcional
                pode_gravar = inv.ticket and veredito.aprovado
                if pode_gravar and confirmar is not None:
                    autorizado = await confirmar(
                        f"Publicar RCA para {inv.cliente['nome'] if inv.cliente else '?'} "
                        f"(confianca {inv.confianca:.0%})? Acao irreversivel: fecha ticket no Mongo."
                    )
                    if not autorizado:
                        inv.encerrado_por_humano = True
                        pode_gravar = False
                if pode_gravar:
                    inv.rca_id = analista.registrar_rca(
                        inv.ticket["_id"], _conclusao(inv), inv.evidencias
                    )
                if inv.ticket:
                    rca_writer.salvar(inv.relatorio, inv.rca_id or inv.ticket["_id"])
                if pode_gravar and os.getenv("SENTINEL_GERAR_BACKLOG", "1") != "0":
                    inv.backlog_path = await _gerar_backlog(inv)
                _persistir_trace(inv, veredito)
            # Se auto_publicar=False: parou no preview. App.py chama publicar(inv) depois.
            inv.estado = State.DONE

    _snapshot(State.DONE)
    return inv


if __name__ == "__main__":
    import sys

    flags = {"--no-reset", "--interactive", "-i"}
    args = [a for a in sys.argv[1:] if a not in flags]
    no_reset = "--no-reset" in sys.argv[1:]
    interativo = "--interactive" in sys.argv[1:] or "-i" in sys.argv[1:]
    pergunta = " ".join(args) or "Por que o sistema da Acme esta caindo?"
    if not no_reset:
        try:
            from agents.seed_helper import reset_tickets
            r = reset_tickets()
            if r["tickets_reabertos"] or r["rcas_apagados"]:
                print(f"[auto-reset] {r['tickets_reabertos']} tickets reabertos, {r['rcas_apagados']} RCAs apagados")
        except Exception as e:
            print(f"[auto-reset] falhou ({type(e).__name__}) — seguindo mesmo assim")
    # forca stdout em UTF-8 (Windows console default eh cp1252 e quebra com emojis)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if interativo:
        async def _perguntar(q: str) -> str:
            print(f"\n[pergunta] {q}")
            return input("> ").strip()

        async def _confirmar(q: str) -> bool:
            print(f"\n[confirmar] {q}")
            return input("s/n > ").strip().lower().startswith("s")

        resultado = asyncio.run(run(pergunta, perguntar=_perguntar, confirmar=_confirmar))
    else:
        resultado = asyncio.run(run(pergunta))
    print(resultado.relatorio)
    print("\n---")
    encerrado = " (encerrado por humano)" if resultado.encerrado_por_humano else ""
    print(f"rca_id={resultado.rca_id} confianca={resultado.confianca:.0%} iter={resultado.iteracao}{encerrado}")
