"""Memory Adapter — recupera contexto de longo prazo + episodios antes da investigacao.

Estrutura:
  memory_store/longa/<cliente_key>.yaml   — fatos sobre o cliente (stack, SLOs, peculiaridades)
  memory_store/episodica/<cliente_key>.yaml — episodios (incidentes passados resumidos)
  reflection_store/licoes/*.yaml          — licoes generalizaveis (fase 4)

Politicas (espelham contracts/memory.md do aula15):
  - so retorna fatos se memoria estiver habilitada (SENTINEL_MEMORY_DISABLED != "1")
  - filtra por cliente identificado na pergunta
  - max 5 fragmentos por categoria (controla budget de contexto)
  - nunca expoe secrets — yaml manual, sem dados sensiveis

API:
  recuperar(pergunta, cliente_nome) -> dict{fatos, episodios, licoes}
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
LONGA_DIR = ROOT / "memory_store" / "longa"
EPISODICA_DIR = ROOT / "memory_store" / "episodica"
LICOES_DIR = ROOT / "reflection_store" / "licoes"

MAX_POR_CATEGORIA = 5


def habilitada() -> bool:
    return os.environ.get("SENTINEL_MEMORY_DISABLED") != "1"


def _cliente_key(nome: str | None) -> str | None:
    """Normaliza nome do cliente em chave de arquivo (primeiro nome em minusculas)."""
    if not nome:
        return None
    return nome.split()[0].lower()


def _carregar_yaml(arq: Path) -> dict:
    if not arq.exists():
        return {}
    try:
        data = yaml.safe_load(arq.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _carregar_fatos(cliente_key: str) -> list[str]:
    data = _carregar_yaml(LONGA_DIR / f"{cliente_key}.yaml")
    fatos = data.get("fatos", []) or []
    return [str(f) for f in fatos][:MAX_POR_CATEGORIA]


def _carregar_episodios(cliente_key: str) -> list[dict]:
    data = _carregar_yaml(EPISODICA_DIR / f"{cliente_key}.yaml")
    eps = data.get("episodios", []) or []
    return [e for e in eps if isinstance(e, dict)][:MAX_POR_CATEGORIA]


def _carregar_licoes() -> list[dict]:
    """Licoes sao globais (nao filtradas por cliente — sao generalizaveis)."""
    if not LICOES_DIR.exists():
        return []
    licoes = []
    for arq in sorted(LICOES_DIR.glob("*.yaml")):
        lic = _carregar_yaml(arq)
        if lic.get("licao"):
            licoes.append(lic)
    return licoes[:MAX_POR_CATEGORIA]


def recuperar(pergunta: str, cliente_nome: str | None = None) -> dict[str, Any]:
    """Recupera contexto de memoria pra uma pergunta + cliente.

    Retorna dict com chaves: fatos, episodios, licoes, habilitada, cliente_key.
    Quando SENTINEL_MEMORY_DISABLED=1 retorna estrutura vazia (no-op controlado).
    """
    if not habilitada():
        return {"fatos": [], "episodios": [], "licoes": [], "habilitada": False, "cliente_key": None}

    key = _cliente_key(cliente_nome)
    return {
        "fatos": _carregar_fatos(key) if key else [],
        "episodios": _carregar_episodios(key) if key else [],
        "licoes": _carregar_licoes(),
        "habilitada": True,
        "cliente_key": key,
    }


def resumir_para_conclusao(ctx: dict) -> str:
    """Gera 1 linha de contexto historico pra anexar na conclusao do RCA.

    Retorna "" quando nao ha nada util a injetar (memoria desabilitada ou vazia).
    """
    if not ctx.get("habilitada"):
        return ""
    partes = []
    if ctx["fatos"]:
        partes.append(ctx["fatos"][0])
    if ctx["episodios"]:
        ep = ctx["episodios"][0]
        resumo = ep.get("resumo") or ep.get("descricao") or ""
        if resumo:
            partes.append(f"episodio: {resumo}")
    if not partes:
        return ""
    return "Contexto historico: " + " | ".join(partes)
