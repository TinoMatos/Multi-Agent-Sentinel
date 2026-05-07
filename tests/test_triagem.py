"""Teste end-to-end da state machine em modo degradado.

Sem OPENROUTER_API_KEY (garantido pelo conftest), Triagem cai nos fallbacks
deterministicos do Mongo — entao o cenario plantado no `mongo_seed` deve
fechar o ticket e gerar um RCA salvo em disco.
"""
from __future__ import annotations

import pytest

from agents import rca_writer, triagem


@pytest.mark.asyncio
async def test_investigacao_acme_fecha_ticket(mongo_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)

    inv = await triagem.run("Por que o sistema da Acme esta caindo?")

    assert inv.estado == triagem.State.DONE
    assert inv.cliente is not None
    assert inv.cliente["nome"] == "Acme Corp"
    assert inv.ticket is not None
    assert any(e["tipo"] == "commit" for e in inv.evidencias)
    assert inv.relatorio.startswith("# RCA")
    assert any(p.suffix == ".md" for p in tmp_path.iterdir())


@pytest.mark.asyncio
async def test_cliente_inexistente_nao_quebra(mongo_seed):
    inv = await triagem.run("Por que a Inexistente SA esta caindo?")
    assert inv.estado == triagem.State.DONE
    assert inv.cliente is None
    assert inv.rca_id is None  # nao registra RCA sem ticket


@pytest.mark.asyncio
async def test_state_machine_respeita_max_iter(mongo_seed, monkeypatch):
    # forca limite de 1 iteracao -> deve estourar BudgetExceeded
    from guards import safeguards

    monkeypatch.setattr(safeguards, "Limits", lambda: safeguards.Limits.__class__(  # type: ignore[misc]
        max_iterations=0, token_budget=10, agent_timeout_s=1
    ) if False else type("L", (), {"max_iterations": 0, "token_budget": 10, "agent_timeout_s": 1})())

    with pytest.raises(safeguards.BudgetExceeded):
        await triagem.run("Acme")


@pytest.mark.asyncio
async def test_confianca_capada_sem_grafana(mongo_seed):
    """Sem GRAFANA_* env, confianca deve ficar <= 70% mesmo com varias evidencias."""
    inv = await triagem.run("Por que a Acme esta caindo?")
    grafana_real = [e for e in inv.evidencias if e["tipo"] == "grafana" and "degradado" not in e["nota"]]
    if not grafana_real:
        assert inv.confianca <= 0.70
