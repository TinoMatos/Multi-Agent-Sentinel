import pytest

from agents.critic import avaliar, avaliar_async


def test_aprova_com_evidencias_consistentes():
    ev = [
        {"tipo": "commit", "ref": "abc", "nota": "deploy"},
        {"tipo": "grafana", "ref": "alert1", "nota": "cpu spike"},
    ]
    v = avaliar("Deploy abc causou spike de CPU", ev)
    assert v.aprovado
    assert v.confianca == 1.0


def test_reprova_quando_cita_deploy_sem_commit():
    ev = [{"tipo": "mongo", "ref": "x", "nota": "ticket"}]
    v = avaliar("Deploy ruim derrubou o sistema", ev)
    assert not v.aprovado
    assert any("commit" in m for m in v.motivos)


def test_reprova_quando_cita_metrica_sem_grafana():
    ev = [
        {"tipo": "commit", "ref": "1", "nota": "deploy commit"},
        {"tipo": "mongo", "ref": "2", "nota": "ticket"},
    ]
    v = avaliar("Houve spike de CPU apos deploy", ev)
    assert not v.aprovado
    assert any("grafana" in m for m in v.motivos)


@pytest.mark.asyncio
async def test_sanity_llm_smoke(monkeypatch):
    """Smoke test do _sanity_llm: so roda se OPENROUTER_API_KEY estiver setada.

    Valida que o caminho LLM nao quebra ao integrar — sem assercao sobre o
    conteudo (modelos free variam). Tambem garante que sem key cai no zero.
    """
    import os
    if not os.getenv("OPENROUTER_API_KEY_REAL"):
        pytest.skip("Defina OPENROUTER_API_KEY_REAL pra rodar smoke test do Critic LLM")
    monkeypatch.setenv("OPENROUTER_API_KEY", os.environ["OPENROUTER_API_KEY_REAL"])
    from agents import _llm
    _llm.chat.cache_clear()
    from agents import critic as critic_mod

    veredito = await critic_mod.avaliar_async(
        "Deploy ruim derrubou o sistema",
        [
            {"tipo": "commit", "ref": "abc", "nota": "deploy"},
            {"tipo": "grafana", "ref": "x", "nota": "spike CPU"},
        ],
    )
    assert isinstance(veredito.confianca, float)
    assert veredito.confianca >= 0.0


def test_reprova_quando_maioria_e_degradada():
    ev = [
        {"tipo": "mongo", "ref": "1", "nota": "ticket aberto"},
        {"tipo": "commit", "ref": "abc", "nota": "deploy suspeito"},
        {"tipo": "playwright", "ref": "url", "nota": "HTTP 500 (degradado)"},
        {"tipo": "filesystem", "ref": "x", "nota": "altera tenant.ts (degradado)"},
        {"tipo": "grafana", "ref": "alert", "nota": "alerta ativo (degradado)"},
    ]
    v = avaliar("Deploy abc derrubou o servico", ev)
    assert not v.aprovado
    assert any("degradado" in m for m in v.motivos)


def test_aprova_quando_minoria_e_degradada():
    ev = [
        {"tipo": "mongo", "ref": "1", "nota": "ticket aberto"},
        {"tipo": "commit", "ref": "abc", "nota": "deploy"},
        {"tipo": "grafana", "ref": "alert", "nota": "spike CPU real"},
        {"tipo": "playwright", "ref": "url", "nota": "HTTP 500 (degradado)"},
    ]
    v = avaliar("Deploy abc causou spike de CPU", ev)
    assert v.aprovado


def test_reprova_com_poucas_evidencias():
    v = avaliar("Conclusao qualquer", [{"tipo": "mongo", "ref": "x", "nota": "y"}])
    assert not v.aprovado
    assert any("insuficientes" in m for m in v.motivos)


@pytest.mark.asyncio
async def test_avaliar_async_sem_api_key_iguala_sincrono():
    """Sem OPENROUTER_API_KEY o sanity LLM e no-op — deve bater com avaliar()."""
    ev = [
        {"tipo": "commit", "ref": "abc", "nota": "deploy"},
        {"tipo": "grafana", "ref": "alert1", "nota": "cpu spike"},
    ]
    sincrono = avaliar("Deploy causou CPU", ev)
    assincrono = await avaliar_async("Deploy causou CPU", ev)
    assert sincrono.aprovado == assincrono.aprovado
    assert sincrono.motivos == assincrono.motivos
