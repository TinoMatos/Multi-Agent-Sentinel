"""Tracking de tokens/custo por investigacao.

Coleta usage dos AIMessages do LangChain e estima custo usando uma tabela
local (config/precos.json). Modelo nao listado: custo retorna None.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PRECOS_PATH = Path(__file__).resolve().parent.parent / "config" / "precos.json"


@dataclass
class Telemetria:
    chamadas: list[dict[str, Any]] = field(default_factory=list)

    def registrar(self, agente: str, modelo: str, prompt_tokens: int, completion_tokens: int):
        self.chamadas.append({
            "agente": agente, "modelo": modelo,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        })

    @property
    def total_tokens(self) -> int:
        return sum(c["prompt_tokens"] + c["completion_tokens"] for c in self.chamadas)

    @property
    def custo_usd(self) -> float | None:
        precos = _carregar_precos()
        if not precos:
            return None
        total = 0.0
        for c in self.chamadas:
            p = precos.get(c["modelo"])
            if not p:
                continue
            total += (c["prompt_tokens"] / 1_000_000) * p.get("input", 0)
            total += (c["completion_tokens"] / 1_000_000) * p.get("output", 0)
        return total

    def resumo(self) -> dict[str, Any]:
        return {
            "chamadas": len(self.chamadas),
            "tokens": self.total_tokens,
            "custo_usd": self.custo_usd,
            "por_agente": self._agrupar_por("agente"),
        }

    def _agrupar_por(self, campo: str) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for c in self.chamadas:
            k = c[campo]
            d = out.setdefault(k, {"chamadas": 0, "tokens": 0})
            d["chamadas"] += 1
            d["tokens"] += c["prompt_tokens"] + c["completion_tokens"]
        return out


def extrair_usage(resp: Any) -> tuple[int, int]:
    """Extrai (prompt_tokens, completion_tokens) de um AIMessage do LangChain."""
    meta = getattr(resp, "usage_metadata", None)
    if meta:
        return (meta.get("input_tokens", 0) or 0, meta.get("output_tokens", 0) or 0)
    rmd = getattr(resp, "response_metadata", {}) or {}
    usage = rmd.get("token_usage") or rmd.get("usage") or {}
    return (
        usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0) or 0,
        usage.get("completion_tokens", 0) or usage.get("output_tokens", 0) or 0,
    )


def _carregar_precos() -> dict[str, dict[str, float]]:
    try:
        return json.loads(_PRECOS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
