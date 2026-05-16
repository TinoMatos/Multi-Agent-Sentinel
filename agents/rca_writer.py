"""Geracao do RCA final em markdown.

Mantem `render_rca`/`salvar` (template puro) e adiciona um loop ReAct
(`executar_react`) que segue o contrato em `architectures/react/planner.md`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

PROXIMA_ACAO_CHAMAR = "CHAMAR_FERRAMENTA"
PROXIMA_ACAO_FINALIZAR = "FINALIZAR"
PROXIMA_ACAO_PERGUNTAR = "PERGUNTAR_USUARIO"

REGRAS_REACT = [
    "SEMPRE incluir raciocinio antes de decidir a proxima acao",
    "raciocinio deve conter: (1) o que sei, (2) o que falta, (3) por que escolhi esta acao",
    "nunca retornar texto livre fora do JSON",
    "cada etapa deve avancar em direcao ao objetivo",
    "se nao houve progresso, mudar de estrategia",
    "so FINALIZAR quando todas as evidencias necessarias foram coletadas",
]


def render_rca(
    cliente: str,
    pergunta: str,
    conclusao: str,
    evidencias: list[dict[str, Any]],
    confianca: float,
    iteracao: int,
    ressalvas: list[str] | None = None,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    linhas = [
        f"# RCA — {cliente}",
        "",
        f"_Gerado em {ts} pelo Multi-Agent Sentinel_",
        "",
        f"**Pergunta original:** {pergunta}",
        "",
        f"**Confianca:** {confianca:.0%}  |  **Iteracoes:** {iteracao}",
        "",
        "## Conclusao",
        "",
        conclusao,
        "",
        "## Evidencias",
        "",
        "| # | Tipo | Referencia | Nota |",
        "|---|---|---|---|",
    ]
    for i, e in enumerate(evidencias, 1):
        linhas.append(f"| {i} | `{e['tipo']}` | `{e['ref']}` | {e['nota']} |")
    if ressalvas:
        linhas += ["", "## Ressalvas do Critic", ""]
        linhas += [f"- {m}" for m in ressalvas]
    return "\n".join(linhas) + "\n"


def salvar(markdown: str, ticket_id: Any) -> Path:
    from guards.output_guard import sanitize

    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"rca_{ticket_id}.md"
    path.write_text(sanitize(markdown), encoding="utf-8")
    return path


def _validar_passo(passo: dict[str, Any]) -> None:
    if "raciocinio" not in passo or not passo["raciocinio"]:
        raise ValueError("passo sem 'raciocinio'")
    if "proxima_acao" not in passo:
        raise ValueError("passo sem 'proxima_acao'")
    if "criterio_sucesso" not in passo:
        raise ValueError("passo sem 'criterio_sucesso'")
    acao = passo["proxima_acao"]
    if acao == PROXIMA_ACAO_CHAMAR and not passo.get("nome_ferramenta"):
        raise ValueError("CHAMAR_FERRAMENTA exige 'nome_ferramenta'")
    if acao == PROXIMA_ACAO_PERGUNTAR and not passo.get("pergunta"):
        raise ValueError("PERGUNTAR_USUARIO exige 'pergunta'")


def executar_react(
    cliente: str,
    pergunta: str,
    planner: Callable[[dict[str, Any]], dict[str, Any]],
    max_iteracoes: int = 8,
) -> dict[str, Any]:
    """Roda o loop Reason+Act ate FINALIZAR ou esgotar iteracoes.

    `planner` recebe o estado e retorna o JSON descrito em planner.md.
    Ferramentas disponiveis:
      - registrar_evidencia(tipo, ref, nota)
      - finalizar(conclusao, confianca, ressalvas?)
    """
    estado: dict[str, Any] = {
        "cliente": cliente,
        "pergunta": pergunta,
        "evidencias": [],
        "trace": [],
        "iteracao": 0,
        "finalizado": False,
        "conclusao": None,
        "confianca": 0.0,
        "ressalvas": [],
    }

    for i in range(1, max_iteracoes + 1):
        estado["iteracao"] = i
        passo = planner(estado)
        _validar_passo(passo)
        estado["trace"].append(passo)

        acao = passo["proxima_acao"]
        if acao == PROXIMA_ACAO_FINALIZAR:
            args = passo.get("argumentos_ferramenta") or {}
            estado["conclusao"] = args.get("conclusao", "")
            estado["confianca"] = float(args.get("confianca", 0.0))
            estado["ressalvas"] = list(args.get("ressalvas") or [])
            estado["finalizado"] = True
            break
        if acao == PROXIMA_ACAO_PERGUNTAR:
            estado["pergunta_pendente"] = passo["pergunta"]
            break
        if acao == PROXIMA_ACAO_CHAMAR:
            nome = passo["nome_ferramenta"]
            args = passo.get("argumentos_ferramenta") or {}
            if nome == "registrar_evidencia":
                estado["evidencias"].append({
                    "tipo": args["tipo"], "ref": args["ref"], "nota": args["nota"],
                })
            elif nome == "finalizar":
                estado["conclusao"] = args.get("conclusao", "")
                estado["confianca"] = float(args.get("confianca", 0.0))
                estado["ressalvas"] = list(args.get("ressalvas") or [])
                estado["finalizado"] = True
                break
            else:
                raise ValueError(f"ferramenta desconhecida: {nome}")
        else:
            raise ValueError(f"proxima_acao invalida: {acao}")

    if estado["finalizado"]:
        estado["markdown"] = render_rca(
            cliente=cliente,
            pergunta=pergunta,
            conclusao=estado["conclusao"] or "",
            evidencias=estado["evidencias"],
            confianca=estado["confianca"],
            iteracao=estado["iteracao"],
            ressalvas=estado["ressalvas"] or None,
        )
    return estado


def planner_prompt() -> str:
    """Prompt do sistema reutilizavel para LLMs que implementam o planner."""
    schema = {
        "raciocinio": "string (obrigatorio)",
        "proxima_acao": "CHAMAR_FERRAMENTA | FINALIZAR | PERGUNTAR_USUARIO",
        "nome_ferramenta": "registrar_evidencia | finalizar (se CHAMAR_FERRAMENTA)",
        "argumentos_ferramenta": "objeto",
        "criterio_sucesso": "string (obrigatorio)",
        "pergunta": "string (se PERGUNTAR_USUARIO)",
    }
    regras = "\n".join(f"- {r}" for r in REGRAS_REACT)
    return (
        "Voce e o planner ReAct do rca_writer.\n"
        "Responda APENAS JSON valido seguindo este schema:\n"
        f"{json.dumps(schema, indent=2, ensure_ascii=False)}\n\n"
        f"Regras:\n{regras}\n"
    )
