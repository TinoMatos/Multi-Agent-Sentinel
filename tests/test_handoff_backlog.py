"""Handoff Triagem -> Backlog Decomposer apos RCA aprovado."""
from __future__ import annotations

from pathlib import Path

import pytest

from agents import rca_writer, triagem


@pytest.mark.asyncio
async def test_rca_aprovado_dispara_backlog(mongo_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)
    # forca aprovacao do Critic (em modo degradado normal a Acme eh vetada)
    monkeypatch.setattr(triagem.critic, "_heuristicas", lambda c, e: [])

    inv = await triagem.run("Por que o sistema da Acme esta caindo?")

    assert inv.rca_id is not None
    assert inv.backlog_path is not None
    backlog_file = Path(inv.backlog_path)
    assert backlog_file.exists()
    conteudo = backlog_file.read_text(encoding="utf-8")
    assert "Backlog" in conteudo
    assert "Epicos" in conteudo


@pytest.mark.asyncio
async def test_rca_vetado_nao_gera_backlog(mongo_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)
    # heuristica default veta Acme em degradado — desliga memoria pra preservar baseline
    monkeypatch.setenv("SENTINEL_MEMORY_DISABLED", "1")
    inv = await triagem.run("Por que o sistema da Acme esta caindo?")
    assert inv.rca_id is None
    assert inv.backlog_path is None


@pytest.mark.asyncio
async def test_opt_out_via_env(mongo_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(triagem.critic, "_heuristicas", lambda c, e: [])
    monkeypatch.setenv("SENTINEL_GERAR_BACKLOG", "0")

    inv = await triagem.run("Por que o sistema da Acme esta caindo?")
    assert inv.rca_id is not None  # RCA gravado normalmente
    assert inv.backlog_path is None  # backlog desligado
