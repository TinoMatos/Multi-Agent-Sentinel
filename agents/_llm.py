"""LLM factory: ChatOpenAI apontado para OpenRouter.

Modelos sao definidos em `config/llm.json` (editavel sem mexer em codigo).
Precedencia: env var > config file > default hardcoded.

  SENTINEL_MODEL       sobrescreve config.main.model
  SENTINEL_MODEL_FAST  sobrescreve config.fast.model
  OPENROUTER_BASE_URL  sobrescreve config.base_url
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "llm.json"
_DEFAULTS = {
    "main": {"model": "anthropic/claude-sonnet-4.5", "temperature": 0.0},
    "fast": {"model": "anthropic/claude-haiku-4.5", "temperature": 0.0},
    "base_url": "https://openrouter.ai/api/v1",
}


@lru_cache(maxsize=1)
def _config() -> dict:
    if not _CONFIG_PATH.exists():
        return _DEFAULTS
    try:
        raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return {
            "main": {**_DEFAULTS["main"], **raw.get("main", {})},
            "fast": {**_DEFAULTS["fast"], **raw.get("fast", {})},
            "base_url": raw.get("base_url", _DEFAULTS["base_url"]),
        }
    except (json.JSONDecodeError, OSError):
        return _DEFAULTS


def _have_key() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


@lru_cache(maxsize=4)
def chat(model: str | None = None, temperature: float | None = None):
    """Retorna um ChatOpenAI configurado para OpenRouter, ou None em modo degradado."""
    if not _have_key():
        return None
    from langchain_openai import ChatOpenAI  # type: ignore

    cfg = _config()
    resolved_model = model or os.getenv("SENTINEL_MODEL") or cfg["main"]["model"]
    resolved_temp = temperature if temperature is not None else cfg["main"].get("temperature", 0.0)

    return ChatOpenAI(
        model=resolved_model,
        temperature=resolved_temp,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL", cfg["base_url"]),
        default_headers={
            "HTTP-Referer": "https://github.com/sentinel",
            "X-Title": "Multi-Agent Sentinel",
        },
    )


def fast(temperature: float | None = None):
    """Modelo barato para Critic e tarefas curtas."""
    cfg = _config()
    model = os.getenv("SENTINEL_MODEL_FAST") or cfg["fast"]["model"]
    temp = temperature if temperature is not None else cfg["fast"].get("temperature", 0.0)
    return chat(model, temp)


def disponivel() -> bool:
    return _have_key()
