"""Ponte LangChain + MCP para os sub-agentes.

Usa `langchain-mcp-adapters` para carregar tools dos MCPs configurados em
`mcp/config.json`, e `langgraph.prebuilt.create_react_agent` para rodar um
ReAct loop com OpenRouter (via _llm.chat()).

Em modo degradado (sem OPENROUTER_API_KEY ou pacotes faltando), retorna [].
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agents import _llm

_MCP_CONFIG_PATH = Path(__file__).resolve().parent.parent / "mcp" / "config.json"



def _load_mcp_servers(nomes: list[str]) -> dict[str, Any]:
    if not _MCP_CONFIG_PATH.exists():
        return {}
    cfg = json.loads(_MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    todos = cfg.get("mcpServers", {})
    # langchain-mcp-adapters espera o campo `transport` por servidor
    out: dict[str, Any] = {}
    for n in nomes:
        if n not in todos:
            continue
        spec = dict(todos[n])
        spec.setdefault("transport", "stdio")
        spec.setdefault("args", [])
        # expande ${VAR} no env a partir do os.environ
        if "env" in spec:
            spec["env"] = {
                k: os.path.expandvars(v) if isinstance(v, str) else v
                for k, v in spec["env"].items()
            }
        out[n] = spec
    return out


def _parse_evidencias(texto: str) -> list[dict[str, Any]]:
    m = re.search(r"\[\s*\{.*?\}\s*\]", texto, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [e for e in data if isinstance(e, dict) and "tipo" in e]


async def query_mcp(servers: list[str], system: str, user: str, fast: bool = False) -> list[dict[str, Any]]:
    llm = _llm.fast() if fast else _llm.chat()
    if llm is None:
        return []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient  # type: ignore
        from langgraph.prebuilt import create_react_agent  # type: ignore
    except ImportError:
        return []

    mcp_servers = _load_mcp_servers(servers)
    if not mcp_servers:
        return []

    try:
        client = MultiServerMCPClient(mcp_servers)
        tools = await client.get_tools()
        for t in tools:
            t.handle_tool_error = True
        agent = create_react_agent(llm, tools, prompt=system)
        msgs_in: list[dict] = [{"role": "user", "content": user}]
        result = await agent.ainvoke({"messages": msgs_in})
    except Exception as e:
        # MCP indisponivel, query malformada, timeout do servidor, etc. -> modo degradado
        import logging
        # destrincha ExceptionGroup pra mostrar a causa real
        def _achatar(exc, prof=0):
            if prof > 4:
                return [f"{type(exc).__name__}: {str(exc)[:200]}"]
            if hasattr(exc, "exceptions") and exc.exceptions:  # type: ignore[attr-defined]
                out = []
                for x in exc.exceptions:  # type: ignore[attr-defined]
                    out.extend(_achatar(x, prof + 1))
                return out
            return [f"{type(exc).__name__}: {str(exc)[:200]}"]
        folhas = _achatar(e)
        detalhe = f"{type(e).__name__} -> [{' | '.join(folhas)}]"
        logging.getLogger(__name__).warning("MCP %s indisponivel: %s", servers, detalhe)
        return []

    msgs = result.get("messages", [])
    texto = ""
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.strip():
            texto = content
            break
    parsed = _parse_evidencias(texto)
    if not parsed and texto:
        import logging
        logging.getLogger(__name__).warning(
            "MCP %s: LLM retornou %d chars, %d msgs, mas nao parseou JSON. Reforcando formato.",
            servers, len(texto), len(msgs),
        )
        # 1 retry: pede explicitamente pra reformatar como lista JSON pura
        try:
            retry_msgs = msgs_in + [
                {"role": "assistant", "content": texto},
                {"role": "user", "content": (
                    "Sua resposta nao esta em formato JSON parseavel. "
                    "Reescreva APENAS a lista JSON pura (comecando com [ e terminando com ]), "
                    "sem nenhum texto antes ou depois. Se nao tiver nada relevante a relatar, "
                    "responda exatamente: []"
                )},
            ]
            result2 = await agent.ainvoke({"messages": retry_msgs})
            msgs2 = result2.get("messages", [])
            for m in reversed(msgs2):
                content = getattr(m, "content", None)
                if isinstance(content, str) and content.strip():
                    parsed = _parse_evidencias(content)
                    break
        except Exception:
            pass
    return parsed
