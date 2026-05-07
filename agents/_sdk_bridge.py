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


async def query_mcp(servers: list[str], system: str, user: str) -> list[dict[str, Any]]:
    llm = _llm.chat()
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
        agent = create_react_agent(
            llm, tools, prompt=system,
            # erros de tool ficam como mensagem para o LLM ajustar e nao explodem o run
            # (default ja tenta isso, mas garantimos com string customizada)
        )
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user}]})
    except Exception as e:
        # MCP indisponivel, query malformada, timeout do servidor, etc. -> modo degradado
        import logging
        logging.getLogger(__name__).warning("MCP %s indisponivel: %s", servers, type(e).__name__)
        return []

    msgs = result.get("messages", [])
    texto = ""
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.strip():
            texto = content
            break
    return _parse_evidencias(texto)
