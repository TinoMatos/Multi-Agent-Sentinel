"""Observabilidade: Grafana MCP — metricas e alertas ao vivo.

Fase 3: usa Claude Agent SDK com o MCP `grafana` para consultar alertas e
series temporais no momento da investigacao. Em modo degradado (sem GRAFANA_*
no env), retorna lista vazia — Triagem capa confianca em 70% como combinado.
"""
from __future__ import annotations

import os
from typing import Any

from agents._sdk_bridge import query_mcp


SYSTEM = (
    "Voce e o agente de Observabilidade. Use as tools do MCP grafana para listar "
    "alertas ATIVOS e qualquer spike de CPU/latencia/error_rate na ultima hora "
    "que possa estar relacionado a pergunta. Retorne ate 5 itens, cada um como "
    "JSON: {tipo:'grafana', ref:<alert_id|panel_id>, nota:<descricao curta>}. "
    "Nada alem da lista JSON."
)


def disponivel() -> bool:
    from agents import _llm
    return bool(os.getenv("GRAFANA_URL") and os.getenv("GRAFANA_API_KEY") and _llm.disponivel())


async def coletar(pergunta: str) -> list[dict[str, Any]]:
    if not disponivel():
        return []
    return await query_mcp(servers=["grafana"], system=SYSTEM, user=pergunta, fast=True)
