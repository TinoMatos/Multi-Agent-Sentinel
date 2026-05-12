"""Critic: valida se as evidencias coletadas sustentam a conclusao.

Heuristicas deterministicas + sanity check LLM via LangChain/OpenRouter
(modelo `fast` — Haiku por default). Sem OPENROUTER_API_KEY, cai para
heuristica pura.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agents import _llm


@dataclass
class Veredito:
    aprovado: bool
    confianca: float
    motivos: list[str]


def _heuristicas(conclusao: str, evidencias: list[dict[str, Any]]) -> list[str]:
    motivos: list[str] = []
    tipos = {e.get("tipo") for e in evidencias}
    if len(evidencias) < 2:
        motivos.append("evidencias insuficientes (<2)")
    if "commit" not in tipos and "deploy" in conclusao.lower():
        motivos.append("conclusao cita deploy mas nao ha evidencia tipo=commit")
    if "grafana" not in tipos and any(k in conclusao.lower() for k in ("cpu", "latencia", "spike")):
        motivos.append("conclusao cita metrica mas nao ha evidencia tipo=grafana")
    # Modo degradado: se a maioria das evidencias vem de fallback deterministico,
    # nao houve confirmacao externa real — vetar publicacao.
    degradadas = sum(1 for e in evidencias if "degradado" in (e.get("nota") or "").lower())
    if evidencias and degradadas / len(evidencias) > 0.5:
        motivos.append(
            f"maioria das evidencias em modo degradado ({degradadas}/{len(evidencias)}) — "
            f"sem confirmacao externa via MCP"
        )
    return motivos


async def _sanity_llm(
    conclusao: str,
    evidencias: list[dict[str, Any]],
    telemetria: Any = None,
) -> list[str]:
    llm = _llm.fast()
    if llm is None:
        return []
    prompt = (
        "Voce e um critico de RCA. Dada a conclusao e a lista de evidencias, "
        "responda APENAS um JSON {contradicoes: [str, ...]}. Liste no maximo 3 "
        "contradicoes claras entre conclusao e evidencias. Se nao houver, lista vazia.\n\n"
        f"CONCLUSAO: {conclusao}\n\nEVIDENCIAS: {json.dumps(evidencias, default=str)[:3000]}"
    )
    try:
        resp = await llm.ainvoke(prompt)
        if telemetria is not None:
            from agents._telemetria import extrair_usage
            import os
            modelo = os.getenv("SENTINEL_MODEL_FAST") or _llm._config()["fast"]["model"]
            pt, ct = extrair_usage(resp)
            telemetria.registrar("critic", modelo, pt, ct)
        texto = resp.content if isinstance(resp.content, str) else str(resp.content)
        data = json.loads(texto[texto.find("{") : texto.rfind("}") + 1])
        return [str(c) for c in data.get("contradicoes", [])][:3]
    except Exception:
        return []


def avaliar(conclusao: str, evidencias: list[dict[str, Any]]) -> Veredito:
    motivos = _heuristicas(conclusao, evidencias)
    base = 1.0 - 0.25 * len(motivos)
    return Veredito(aprovado=not motivos, confianca=max(0.0, min(1.0, base)), motivos=motivos)


async def avaliar_async(
    conclusao: str,
    evidencias: list[dict[str, Any]],
    telemetria: Any = None,
) -> Veredito:
    motivos = _heuristicas(conclusao, evidencias)
    motivos += [f"contradicao LLM: {c}" for c in await _sanity_llm(conclusao, evidencias, telemetria)]
    base = 1.0 - 0.20 * len(motivos)
    return Veredito(aprovado=not motivos, confianca=max(0.0, min(1.0, base)), motivos=motivos)
