"""Tecnico: confirmacao ATIVA via filesystem + Playwright (MCPs).

Fase 3: usa o Claude Agent SDK com MCPs em uma unica sessao. O LLM decide
quais tools chamar (ex.: ler runbook, navegar na URL), e devolve uma lista
JSON de evidencias.

Mantemos os helpers deterministicos abaixo — sao usados pelo Critic e por
testes sem API key.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from agents._sdk_bridge import query_mcp


def _build_system() -> str:
    import os
    repo = os.getenv("SENTINEL_GITHUB_REPO", "").strip()
    github_block = ""
    if os.getenv("SENTINEL_USE_GITHUB") == "1" and repo:
        github_block = (
            f" Voce tambem tem acesso ao MCP github (somente leitura) apontando "
            f"para o repositorio `{repo}`. Use APENAS `search_code` para encontrar "
            f"trechos relevantes (nomes de funcao, arquivos, padroes do stacktrace) "
            f"nesse repo. NAO chame get_commit nem get_pull_request com SHAs do "
            f"stacktrace — eles sao IDs internos e nao existem no GitHub. "
            f"NUNCA escreva (sem create issue, sem comment, sem push)."
        )
    return (
        "Voce e o agente Tecnico. Tem acesso aos MCPs filesystem (logs em ./data) "
        "e playwright (navegacao headless)."
        + github_block +
        " Para a hipotese fornecida: (1) leia logs/runbooks relevantes, "
        "(2) navegue na URL do cliente se aplicavel e capture o status HTTP, "
        "(3) se github estiver disponivel, busque por nomes de funcao/arquivo do "
        "stacktrace para mostrar o codigo real. "
        "Devolva uma lista JSON de evidencias no formato "
        "{tipo:'playwright'|'filesystem'|'github', ref:..., nota:...}. "
        "Maximo 6 itens. Nada alem da lista JSON."
    )


SYSTEM = _build_system()  # mantido por compatibilidade; coletar() rebuilda.


def disponivel() -> bool:
    from agents import _llm
    return _llm.disponivel()


async def coletar(hipotese: str) -> list[dict[str, Any]]:
    if not disponivel():
        return []
    import os
    # 1) MCPs essenciais (filesystem + playwright) — sempre
    evidencias = await query_mcp(
        servers=["filesystem", "playwright"],
        system=_build_system(),
        user=hipotese,
    )
    # 2) GitHub MCP em chamada separada — se falhar nao derruba o resto
    if (
        os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        and os.getenv("SENTINEL_USE_GITHUB") == "1"
        and os.getenv("SENTINEL_GITHUB_REPO", "").strip()
    ):
        gh_evid = await query_mcp(
            servers=["github"],
            system=_build_system(),
            user=hipotese,
        )
        evidencias.extend(gh_evid)
    return evidencias


# ---------- helpers deterministicos (usados por testes e Critic) ----------

def commit_dentro_da_janela(commit_ts: datetime, incidente_ts: datetime, janela_min: int = 30) -> bool:
    if commit_ts > incidente_ts:
        return False
    return incidente_ts - commit_ts <= timedelta(minutes=janela_min)


def extrair_sintomas_do_log(log: str, limite_linhas: int = 20) -> list[str]:
    sintomas = []
    for linha in log.splitlines():
        l = linha.strip()
        if not l:
            continue
        if any(k in l.lower() for k in ("error", "exception", "traceback", "fatal", "panic")):
            sintomas.append(l)
        if len(sintomas) >= limite_linhas:
            break
    return sintomas


def confianca_visual(playwright_resultado: dict[str, Any]) -> float:
    status = playwright_resultado.get("http_status")
    if status and status >= 500:
        return 0.95
    if playwright_resultado.get("erro_visivel_no_dom"):
        return 0.85
    if status == 200:
        return 0.10
    return 0.50
