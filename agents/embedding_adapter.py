"""Embedding Adapter — memoria contextual via similaridade semantica.

Espelha aula15/runtime/adapters/embedding_adapter.py, adaptado pra rodar
em modo degradado (sem OPENAI_API_KEY) usando fallback determinístico
baseado em token overlap. Em produção, se OPENAI_API_KEY estiver presente,
usa text-embedding-3-small.

Indice unico em memory_store/contextual/indice.json com fragmentos de
longa + episodica. API:
  indexar(texto, metadados) -> id
  buscar(consulta, max_resultados=None, limiar=None) -> list[fragmentos]
  reindexar() -> int
"""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
CONTEXTUAL_DIR = ROOT / "memory_store" / "contextual"
INDICE_PATH = CONTEXTUAL_DIR / "indice.json"
LONGA_DIR = ROOT / "memory_store" / "longa"
EPISODICA_DIR = ROOT / "memory_store" / "episodica"

LIMIAR_PADRAO = 0.30  # tf-overlap eh mais baixo que cosseno de embedding real
MAX_PADRAO = 5
MODELO_PADRAO = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Provedor de embedding (real ou fallback)
# ---------------------------------------------------------------------------

def _tem_openai() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY")) and os.environ.get(
        "SENTINEL_FORCE_FALLBACK_EMBEDDING"
    ) != "1"


def _tokenizar(texto: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", texto.lower()) if len(t) > 2]


def _embedding_fallback(texto: str) -> list[float]:
    """Vetor de frequencias normalizado em dimensao fixa (hash bucket).

    Determinístico, sem dependencia externa. Não captura semantica real, mas
    suporta similaridade lexica suficiente pro eval didatico.
    """
    dim = 256
    vec = [0.0] * dim
    for tok in _tokenizar(texto):
        idx = hash(tok) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def _embedding_openai(texto: str, modelo: str) -> list[float]:
    from openai import OpenAI  # import local — opcional
    client = OpenAI()
    resp = client.embeddings.create(model=modelo, input=texto)
    return resp.data[0].embedding


def gerar_embedding(texto: str, modelo: str = MODELO_PADRAO) -> list[float]:
    if _tem_openai():
        try:
            return _embedding_openai(texto, modelo)
        except Exception:
            return _embedding_fallback(texto)
    return _embedding_fallback(texto)


def _cosseno(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Indice
# ---------------------------------------------------------------------------

def _carregar_indice() -> list[dict]:
    if not INDICE_PATH.exists():
        return []
    try:
        return json.loads(INDICE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _salvar_indice(indice: list[dict]) -> None:
    CONTEXTUAL_DIR.mkdir(parents=True, exist_ok=True)
    INDICE_PATH.write_text(
        json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def indexar(texto: str, metadados: dict | None = None) -> str:
    from guards.output_guard import sanitize

    emb = gerar_embedding(texto)
    indice = _carregar_indice()
    entrada = {
        "id": f"emb_{uuid.uuid4().hex[:8]}",
        "texto": sanitize(texto),
        "embedding": emb,
        "metadados": metadados or {},
        "timestamp": datetime.now().isoformat(),
    }
    indice.append(entrada)
    _salvar_indice(indice)
    return entrada["id"]


def buscar(consulta: str, max_resultados: int | None = None,
           limiar: float | None = None) -> list[dict]:
    max_r = max_resultados or MAX_PADRAO
    lim = LIMIAR_PADRAO if limiar is None else limiar
    indice = _carregar_indice()
    if not indice:
        return []
    emb_q = gerar_embedding(consulta)

    resultados = []
    for entrada in indice:
        sim = _cosseno(emb_q, entrada.get("embedding") or [])
        if sim >= lim:
            resultados.append({
                "id": entrada["id"],
                "texto": entrada["texto"],
                "similaridade": round(sim, 4),
                "metadados": entrada.get("metadados", {}),
            })
    resultados.sort(key=lambda r: r["similaridade"], reverse=True)
    return resultados[:max_r]


def reindexar() -> int:
    """Reconstroi indice a partir de longa + episodica."""
    indice: list[dict] = []

    def _coletar(diretorio: Path, tipo: str, chave_lista: str, campos_texto: list[str]):
        if not diretorio.exists():
            return
        for arq in sorted(diretorio.glob("*.yaml")):
            try:
                data = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            cliente = data.get("cliente") or arq.stem
            cliente_key = arq.stem.lower()
            itens = data.get(chave_lista) or []
            if chave_lista == "fatos":
                for i, fato in enumerate(itens):
                    texto = str(fato)
                    indice.append({
                        "id": f"emb_{uuid.uuid4().hex[:8]}",
                        "texto": texto,
                        "embedding": gerar_embedding(texto),
                        "metadados": {
                            "tipo": tipo,
                            "cliente_key": cliente_key,
                            "cliente": cliente,
                            "origem": f"{arq.name}#fato_{i}",
                        },
                        "timestamp": datetime.now().isoformat(),
                    })
            else:  # episodios
                for ep in itens:
                    if not isinstance(ep, dict):
                        continue
                    partes = [str(ep.get(c, "")) for c in campos_texto if ep.get(c)]
                    texto = " | ".join(partes)
                    if not texto.strip():
                        continue
                    indice.append({
                        "id": f"emb_{uuid.uuid4().hex[:8]}",
                        "texto": texto,
                        "embedding": gerar_embedding(texto),
                        "metadados": {
                            "tipo": tipo,
                            "cliente_key": cliente_key,
                            "cliente": cliente,
                            "origem": f"{arq.name}#{ep.get('id', '?')}",
                        },
                        "timestamp": datetime.now().isoformat(),
                    })

    _coletar(LONGA_DIR, "longa", "fatos", [])
    _coletar(EPISODICA_DIR, "episodica", "episodios",
             ["resumo", "sintoma", "causa", "resolucao"])

    _salvar_indice(indice)
    return len(indice)


def garantir_indice() -> int:
    """Reindexa se o indice estiver vazio ou inexistente. Retorna tamanho atual."""
    indice = _carregar_indice()
    if indice:
        return len(indice)
    return reindexar()


if __name__ == "__main__":
    n = reindexar()
    print(f"[embedding_adapter] indice contextual reconstruido: {n} fragmentos")
