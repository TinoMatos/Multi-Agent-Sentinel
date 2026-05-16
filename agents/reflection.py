"""Reflection — extrai licoes generalizaveis de execucoes que correram mal.

Espelha aula15: politica de "so o inesperado vira licao". Dispara em:
  - critic veta a investigacao (veredito.aprovado=False)
  - confianca final baixa apos retry (confianca < 0.5 e redelegacoes >= 1)
  - max_iterations atingido sem conclusao
  - excecao no ciclo (capturada em triagem)

Heuristica simples (sem LLM) — extrai padroes do trace. Em producao,
substituir por LLM-as-extractor; aqui e didatico e ja popula lesson_quality.

Politicas (espelham contracts/memory.md):
  - nunca grava secret, token, password, api_key, .env
  - cap em 1 licao por execucao (evita poluicao)
  - so grava se o motivo for "novo" (assinatura nao colide com licao existente)

API:
  extrair_licoes(inv, veredito) -> path | None
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
LICOES_DIR = ROOT / "reflection_store" / "licoes"

PADROES_PROIBIDOS = re.compile(
    r"(?i)(password|api[_-]?key|secret|token|\.env\b|sk-[a-z0-9]+)"
)


def habilitada() -> bool:
    return os.environ.get("SENTINEL_REFLECTION_DISABLED") != "1"


def _gatilho(inv, veredito) -> str | None:
    """Retorna o motivo do gatilho ou None se nao deve extrair."""
    if veredito is not None and not veredito.aprovado:
        motivos = " ".join(veredito.motivos or [])
        return f"critic_vetou: {motivos[:120]}"
    if inv.confianca < 0.5 and inv.redelegacoes >= 1:
        return f"baixa_confianca_apos_retry: {inv.confianca:.2f}"
    max_iter = int(os.environ.get("SENTINEL_MAX_ITERATIONS", "8"))
    if inv.iteracao >= max_iter and not inv.rca_id:
        return f"max_iter_sem_conclusao: {inv.iteracao}"
    return None


def _sanitizar(texto: str) -> str:
    return PADROES_PROIBIDOS.sub("[REDACTED]", texto or "")


def _assinatura(licao_texto: str) -> str:
    """Tokens significativos da licao — usado pra deduplicar."""
    toks = re.findall(r"[a-z0-9]+", licao_texto.lower())
    return " ".join(sorted({t for t in toks if len(t) > 3})[:8])


def _licao_ja_existe(assinatura: str) -> bool:
    if not LICOES_DIR.exists():
        return False
    for arq in LICOES_DIR.glob("*.yaml"):
        try:
            data = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        existente = _assinatura(str(data.get("licao", "")))
        # se >= 80% dos tokens batem, considera duplicada
        a, b = set(assinatura.split()), set(existente.split())
        if not a or not b:
            continue
        overlap = len(a & b) / max(len(a), len(b))
        if overlap >= 0.8:
            return True
    return False


def _redacao_licao(inv, veredito, gatilho: str) -> str | None:
    """Compoe uma licao curta a partir do trace.

    Foca em padrao "<sintoma> + <contexto> -> <acao sugerida>".
    Retorna None se nao tem material o suficiente.
    """
    sintoma = (inv.pergunta or "").strip()
    cliente = (inv.cliente or {}).get("nome") if inv.cliente else None

    motivos_critic = []
    if veredito is not None and veredito.motivos:
        motivos_critic = [m for m in veredito.motivos][:3]

    evidencias_tipos = sorted({e.get("tipo") for e in inv.evidencias if isinstance(e, dict)})
    degradadas = sum(
        1 for e in inv.evidencias
        if "degradado" in (e.get("nota") or "").lower()
    )

    if "critic_vetou" in gatilho:
        base = (
            f"investigacao para sintoma '{sintoma[:80]}'"
            f"{' em ' + cliente if cliente else ''} foi vetada pelo critic"
        )
        if degradadas:
            base += f" com {degradadas} evidencia(s) em fallback"
        if motivos_critic:
            base += f" — motivos: {'; '.join(motivos_critic)}"
        base += ". Antes de publicar, garantir evidencias nao-degradadas e revisar contradicoes."
        return base

    if "baixa_confianca_apos_retry" in gatilho:
        base = (
            f"baixa confianca apos retry em '{sintoma[:80]}'"
            f"{' (' + cliente + ')' if cliente else ''}"
        )
        if not evidencias_tipos:
            base += " sem evidencias coletadas"
        else:
            base += f" com tipos coletados {evidencias_tipos}"
        base += " — investigar se memoria longa do cliente esta desatualizada ou se a redelegacao bateu nas mesmas fontes."
        return base

    if "max_iter_sem_conclusao" in gatilho:
        base = (
            f"max iteracoes atingido para '{sintoma[:80]}'"
            f"{' (' + cliente + ')' if cliente else ''}"
        )
        base += f" — tipos coletados {evidencias_tipos}. Considerar adicionar fato ao memory_store/longa/{(cliente or '').split()[0].lower()}.yaml pra encurtar futuras execucoes."
        return base

    return None


def extrair_licoes(inv, veredito) -> str | None:
    """Hook principal. Retorna path da licao gravada ou None.

    Falha silenciosa — nunca propaga excecao pra triagem.
    """
    if not habilitada():
        return None
    try:
        gatilho = _gatilho(inv, veredito)
        if not gatilho:
            return None

        texto_licao = _redacao_licao(inv, veredito, gatilho)
        if not texto_licao:
            return None
        from guards.output_guard import sanitize as _output_sanitize

        texto_licao = _output_sanitize(_sanitizar(texto_licao))

        assinatura = _assinatura(texto_licao)
        if not assinatura or _licao_ja_existe(assinatura):
            return None

        LICOES_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        cliente_slug = ((inv.cliente or {}).get("nome") or "geral").split()[0].lower()
        path = LICOES_DIR / f"licao_auto_{cliente_slug}_{ts}.yaml"

        registro: dict[str, Any] = {
            "id": f"licao_auto_{cliente_slug}_{ts}",
            "origem": "reflection_automatico",
            "criada_em": datetime.now().date().isoformat(),
            "gatilho": gatilho,
            "cliente": (inv.cliente or {}).get("nome"),
            "licao": texto_licao,
            "trace_id": getattr(inv, "trace_id", None),
        }
        path.write_text(yaml.dump(registro, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return str(path)
    except Exception:
        # politica: reflection nunca derruba investigacao
        return None
