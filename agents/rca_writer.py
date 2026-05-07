"""Geracao do RCA final em markdown (template local)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


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
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"rca_{ticket_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
