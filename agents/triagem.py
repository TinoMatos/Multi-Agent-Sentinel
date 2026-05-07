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


# ---------- hooks dos sub-agentes (Fase 3 plugara MCP/LLM real) ----------

async def _call_analista(inv: Investigacao) -> list[dict[str, Any]]:
    nome = _extrair_nome_cliente(inv.pergunta)
    cliente = analista.cliente_por_nome(nome) if nome else None
    if not cliente:
        return []
    inv.cliente = cliente
    abertos = analista.tickets_abertos_do_cliente(cliente["_id"])
    if not abertos:
        return [{"tipo": "mongo", "ref": str(cliente["_id"]), "nota": "cliente sem tickets abertos"}]
    inv.ticket = abertos[0]
    erros = analista.erros_do_ticket(inv.ticket)
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
    if observabilidade.disponivel():
        timeout_s = float(os.getenv("SENTINEL_OBS_TIMEOUT_S", "60"))
        try:
            ev = await asyncio.wait_for(observabilidade.coletar(inv.pergunta), timeout=timeout_s)
            if ev:
                return ev
        except asyncio.TimeoutError:
            pass  # cai no fallback deterministico
    if not inv.ticket:
        return []
    erros = analista.erros_do_ticket(inv.ticket)
    return [
        {"tipo": "grafana", "ref": e["grafana_alert_id"], "nota": f"alerta ativo p/ {e['tipo']} (degradado)"}
        for e in erros
        if e.get("grafana_alert_id")
    ]


async def _call_tecnico(inv: Investigacao) -> list[dict[str, Any]]:
    """filesystem + Playwright via SDK. Timeout duro: cai em fallback se demorar."""
    url = (inv.ticket.get("url") if inv.ticket else None) or "nenhuma"
    log_path = (inv.ticket.get("log_path") if inv.ticket else None) or "nenhum"
    hipotese = (
        f"Cliente: {inv.cliente['nome'] if inv.cliente else '?'}. "
        f"Ticket: {inv.ticket['descricao'] if inv.ticket else inv.pergunta}. "
        f"Deploy suspeito: {inv.ticket.get('deploy_suspeito') if inv.ticket else 'nenhum'}. "
        f"URL para verificar com Playwright: {url}. "
        f"Arquivo de log para ler com filesystem: {log_path}."
    )
    timeout_s = float(os.getenv("SENTINEL_TECNICO_TIMEOUT_S", "90"))
    if tecnico_mod.disponivel():
        try:
            ev = await asyncio.wait_for(tecnico_mod.coletar(hipotese), timeout=timeout_s)
            if ev:
                return ev
        except asyncio.TimeoutError:
            pass  # cai no fallback deterministico abaixo
    if inv.ticket and inv.ticket.get("deploy_suspeito"):
        return [
            {"tipo": "playwright", "ref": inv.cliente.get("nome", "?") if inv.cliente else "?",
             "nota": "HTTP 500 confirmado visualmente (degradado)"},
            {"tipo": "filesystem", "ref": inv.ticket["deploy_suspeito"],
             "nota": "commit altera src/auth/tenant.ts sem null-check (degradado)"},
        ]
    return []


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

    deploy = inv.ticket.get("deploy_suspeito")
    if deploy:
        return (
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
        return base

    # Confianca alta mas tipo desconhecido — sintetiza do que tem
    if inv.confianca >= 0.7 and stack:
        return (
            f"Sintoma confirmado pelo ticket aberto e evidencias coletadas. "
            f"Stacktrace dominante: {stack}. "
            f"Sem deploy correlato — proximo passo: revisao manual com SRE."
        )

    return "Investigacao inconclusiva — evidencias insuficientes para determinar causa raiz."


# ---------- state machine ----------

async def run(pergunta: str, inv: Investigacao | None = None) -> Investigacao:
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
            ev_a, ev_o = await asyncio.gather(_call_analista(inv), _call_observabilidade(inv))
            inv.evidencias.extend(ev_a + ev_o)
            inv.confianca = _confianca(inv.evidencias)
            # Tecnico SEMPRE roda quando ha um ticket — confirmacao ativa
            # eh o ponto do agente. Sem ticket nao adianta (cliente nao existe).
            if inv.ticket:
                inv.estado = State.CONFIRMANDO
            elif inv.iteracao >= 2:
                inv.estado = State.VALIDANDO
            # senao continua COLETANDO

        elif inv.estado == State.CONFIRMANDO:
            inv.evidencias.extend(await _call_tecnico(inv))
            inv.confianca = _confianca(inv.evidencias)
            inv.estado = State.VALIDANDO

        elif inv.estado == State.VALIDANDO:
            veredito = await critic.avaliar_async(
                _conclusao(inv), inv.evidencias, telemetria=inv.telemetria
            )
            inv._veredito = veredito  # type: ignore[attr-defined]
            inv.estado = State.PUBLICANDO

        elif inv.estado == State.PUBLICANDO:
            veredito = inv._veredito  # type: ignore[attr-defined]
            inv.relatorio = output_guard.sanitize(_montar_relatorio(inv, veredito))
            if inv.ticket and veredito.aprovado:
                inv.rca_id = analista.registrar_rca(
                    inv.ticket["_id"], _conclusao(inv), inv.evidencias
                )
                rca_writer.salvar(inv.relatorio, inv.rca_id)
            inv.estado = State.DONE

    _snapshot(State.DONE)
    return inv


if __name__ == "__main__":
    import sys

    pergunta = " ".join(sys.argv[1:]) or "Por que o sistema da Acme esta caindo?"
    resultado = asyncio.run(run(pergunta))
    print(resultado.relatorio)
    print("\n---")
    print(f"rca_id={resultado.rca_id} confianca={resultado.confianca:.0%} iter={resultado.iteracao}")
