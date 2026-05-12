"""Testes do backlog_decomposer — modo deterministico, sem LLM."""
from __future__ import annotations

import pytest

from agents.backlog_decomposer import decompor, _decompor_deterministico


def test_deterministico_produz_estrutura_minima():
    bl = _decompor_deterministico("permitir cadastro sem suporte humano")
    assert bl.objetivo == "permitir cadastro sem suporte humano"
    assert len(bl.dominios) >= 2
    assert len(bl.epicos) >= 2
    assert all(ep.get("titulo") for ep in bl.epicos)
    assert all(ep.get("stories") for ep in bl.epicos)
    assert len(bl.riscos) >= 3
    assert len(bl.perguntas) >= 2
    assert bl.modo == "deterministico"


def test_stories_tem_criterio_aceite():
    bl = _decompor_deterministico("reduzir latencia do checkout")
    for ep in bl.epicos:
        for s in ep["stories"]:
            assert s.get("titulo")
            assert s.get("criterio_aceite")


def test_render_inclui_secoes_aula06():
    bl = _decompor_deterministico("melhorar conversao do funil")
    md = bl.render()
    assert "Dominios" in md
    assert "Epicos" in md
    assert "Riscos" in md
    assert "Perguntas" in md
    assert "analisar_objetivo -> gerar_epicos" in md


@pytest.mark.asyncio
async def test_decompor_sem_api_key_usa_deterministico():
    """conftest._no_api_key remove OPENROUTER_API_KEY — deve cair em deterministico."""
    bl = await decompor("objetivo qualquer aqui")
    assert bl.modo == "deterministico"
