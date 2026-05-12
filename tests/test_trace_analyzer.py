"""Testes do trace_analyzer — deterministico, sem deps externas."""
from __future__ import annotations

import json

from agents.trace_analyzer import analisar


def _escrever_trace(pasta, ticket_id, **campos):
    base = {
        "ticket_id": ticket_id,
        "rca_id": None,
        "pergunta": "?",
        "cliente": "Acme Corp",
        "confianca": 0.7,
        "iteracao": 5,
        "redelegacoes": 0,
        "veredito_aprovado": True,
        "veredito_motivos": [],
        "evidencias": [],
        "historico_estados": [],
        "gerado_em": "2026-05-12T18:00:00+00:00",
    }
    base.update(campos)
    (pasta / f"trace_{ticket_id}.json").write_text(json.dumps(base), encoding="utf-8")


def test_pasta_inexistente_retorna_zero(tmp_path):
    k = analisar(tmp_path / "nao_existe")
    assert k.total == 0


def test_agrega_taxa_aprovacao(tmp_path):
    _escrever_trace(tmp_path, "t1", veredito_aprovado=True)
    _escrever_trace(tmp_path, "t2", veredito_aprovado=True)
    _escrever_trace(tmp_path, "t3", veredito_aprovado=False, veredito_motivos=["evidencias insuficientes"])
    k = analisar(tmp_path)
    assert k.total == 3
    assert k.aprovados == 2
    assert k.vetados == 1


def test_calcula_pct_degradado(tmp_path):
    _escrever_trace(tmp_path, "t1", evidencias=[
        {"tipo": "mongo", "ref": "x", "degradado": False},
        {"tipo": "playwright", "ref": "y", "degradado": True},
        {"tipo": "filesystem", "ref": "z", "degradado": True},
    ])
    k = analisar(tmp_path)
    assert k.evidencias_total == 3
    assert k.evidencias_degradadas == 2


def test_agrupa_motivos_veto(tmp_path):
    _escrever_trace(tmp_path, "t1", veredito_aprovado=False, veredito_motivos=["evidencias insuficientes (<2)"])
    _escrever_trace(tmp_path, "t2", veredito_aprovado=False, veredito_motivos=["evidencias insuficientes (<2)"])
    _escrever_trace(tmp_path, "t3", veredito_aprovado=False, veredito_motivos=["outro motivo"])
    k = analisar(tmp_path)
    assert k.motivos_veto_mais_comuns["evidencias insuficientes (<2)"] == 2
    assert k.motivos_veto_mais_comuns["outro motivo"] == 1


def test_trace_corrompido_eh_ignorado(tmp_path):
    _escrever_trace(tmp_path, "ok")
    (tmp_path / "trace_quebrado.json").write_text("{nao eh json}", encoding="utf-8")
    k = analisar(tmp_path)
    assert k.total == 1


def test_relatorio_inclui_secoes_principais(tmp_path):
    _escrever_trace(tmp_path, "t1", cliente="Beta SaaS")
    texto = analisar(tmp_path).relatorio()
    assert "Trace Analyzer" in texto
    assert "Beta SaaS" in texto
    assert "Confianca media" in texto
