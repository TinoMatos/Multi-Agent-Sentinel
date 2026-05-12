"""Testes do modo interactive: perguntar (cliente) + confirmar (registrar_rca)."""
from __future__ import annotations

import pytest

from agents import rca_writer, triagem


@pytest.mark.asyncio
async def test_perguntar_resolve_cliente_ausente(mongo_seed, tmp_path, monkeypatch):
    """Quando a pergunta nao identifica cliente, o callback informa e segue."""
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)

    async def perguntar(q):
        assert "cliente" in q.lower()
        return "Acme"

    inv = await triagem.run("alguma coisa estranha esta acontecendo", perguntar=perguntar)
    assert inv.cliente is not None
    assert inv.cliente["nome"] == "Acme Corp"
    assert len(inv.perguntas_humano) == 1
    assert inv.perguntas_humano[0]["r"] == "Acme"


@pytest.mark.asyncio
async def test_sem_perguntar_mantem_falha_silenciosa(mongo_seed):
    """Sem callback: comportamento antigo — bail sem pedir esclarecimento."""
    inv = await triagem.run("alguma coisa estranha esta acontecendo")
    assert inv.cliente is None
    assert inv.perguntas_humano == []


@pytest.mark.asyncio
async def test_confirmar_nega_impede_registrar_rca(mongo_seed, tmp_path, monkeypatch):
    """Critic aprovado + humano nega -> RCA NAO gravado no Mongo (mas markdown salvo)."""
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(triagem.critic, "_heuristicas", lambda c, e: [])  # forca Critic aprovar

    async def confirmar(_q):
        return False

    inv = await triagem.run("Por que o sistema da Acme esta caindo?", confirmar=confirmar)
    assert inv.encerrado_por_humano is True
    assert inv.rca_id is None  # Mongo nao foi tocado
    assert inv.backlog_path is None  # backlog nao roda quando humano negou


@pytest.mark.asyncio
async def test_confirmar_aprova_grava_normalmente(mongo_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(triagem.critic, "_heuristicas", lambda c, e: [])

    async def confirmar(_q):
        return True

    inv = await triagem.run("Por que o sistema da Acme esta caindo?", confirmar=confirmar)
    assert inv.encerrado_por_humano is False
    assert inv.rca_id is not None
