"""Fixtures globais.

Garante que os testes rodam SEM API key (modo degradado) e com Mongo mockado
via mongomock — assim a suite roda em CI sem dependencias externas.
"""
from __future__ import annotations

from datetime import datetime, timezone

import mongomock
import pytest
from bson import ObjectId


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    """Garante modo degradado: sem chamadas LLM reais nos testes."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GRAFANA_URL", raising=False)
    monkeypatch.delenv("GRAFANA_API_KEY", raising=False)
    # limpa cache do factory de LLM
    from agents import _llm
    _llm.chat.cache_clear()


@pytest.fixture(autouse=True)
def _isolar_traces(tmp_path_factory, monkeypatch):
    """Evita que testes polluam data/traces/ com runs de mongomock."""
    from agents import triagem
    monkeypatch.setattr(triagem, "TRACES_DIR", str(tmp_path_factory.mktemp("traces")))


@pytest.fixture
def mongo_seed():
    """Substitui o cliente Mongo do Analista por um mongomock populado."""
    client = mongomock.MongoClient()
    db = client["sentinel"]

    acme_id = ObjectId()
    db.clientes.insert_one(
        {
            "_id": acme_id,
            "nome": "Acme Corp",
            "plano": "enterprise",
            "sla": {"resposta_min": 15, "resolucao_min": 120},
            "contatos": [{"nome": "Joao", "email": "joao@acme.com", "papel": "CTO"}],
            "historico_tickets": [],
        }
    )

    erro_id = ObjectId()
    ticket_id = ObjectId()
    db.erros.insert_one(
        {
            "_id": erro_id,
            "tipo": "HTTP_500",
            "stacktrace": "TypeError: Cannot read properties of undefined (reading 'tenantId')",
            "frequencia": 1432,
            "primeiro_ocorrido": datetime(2026, 5, 5, 14, 28, tzinfo=timezone.utc),
            "ultimo_ocorrido": datetime(2026, 5, 5, 14, 35, tzinfo=timezone.utc),
            "deploy_id": "dpl_x",
            "commit_sha": "a1b2c3d4e5f6",
            "grafana_alert_id": "alert_cpu_spike_97",
            "ticket_relacionado": ticket_id,
        }
    )
    db.tickets.insert_one(
        {
            "_id": ticket_id,
            "clientId": acme_id,
            "descricao": "Site da Acme fora do ar",
            "status": "aberto",
            "prioridade": "P1",
            "erros_correlacionados": [erro_id],
            "deploy_suspeito": "a1b2c3d4e5f6",
            "rca_gerado_id": None,
            "criado_em": datetime(2026, 5, 5, 14, 32, tzinfo=timezone.utc),
            "atualizado_em": datetime(2026, 5, 5, 14, 32, tzinfo=timezone.utc),
        }
    )
    return {"client": client, "db": db, "acme_id": acme_id, "ticket_id": ticket_id, "erro_id": erro_id}


@pytest.fixture(autouse=True)
def _patch_analista_db(mongo_seed, monkeypatch):
    """Faz o modulo `analista` usar o mongomock em vez de Mongo real."""
    from agents import analista

    monkeypatch.setattr(analista, "_client", mongo_seed["client"])
    monkeypatch.setattr(analista, "_db", lambda: mongo_seed["db"])
    yield
