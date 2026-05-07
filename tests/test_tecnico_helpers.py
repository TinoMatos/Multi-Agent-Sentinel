from datetime import datetime, timedelta, timezone

from agents.tecnico import commit_dentro_da_janela, confianca_visual, extrair_sintomas_do_log


def test_commit_dentro_da_janela_true():
    inc = datetime(2026, 5, 5, 14, 30, tzinfo=timezone.utc)
    assert commit_dentro_da_janela(inc - timedelta(minutes=5), inc, janela_min=30)


def test_commit_dentro_da_janela_falso_se_apos_incidente():
    inc = datetime(2026, 5, 5, 14, 30, tzinfo=timezone.utc)
    assert not commit_dentro_da_janela(inc + timedelta(minutes=1), inc)


def test_commit_dentro_da_janela_falso_se_fora_da_janela():
    inc = datetime(2026, 5, 5, 14, 30, tzinfo=timezone.utc)
    assert not commit_dentro_da_janela(inc - timedelta(hours=2), inc, janela_min=30)


def test_extrair_sintomas_de_log():
    log = (
        "INFO server started\n"
        "ERROR Cannot read tenantId\n"
        "DEBUG cache hit\n"
        "Exception in thread main\n"
    )
    s = extrair_sintomas_do_log(log)
    assert len(s) == 2
    assert any("tenantId" in x for x in s)
    assert any("Exception" in x for x in s)


def test_confianca_visual_500_alta():
    assert confianca_visual({"http_status": 503}) >= 0.9


def test_confianca_visual_200_baixa():
    assert confianca_visual({"http_status": 200}) <= 0.2


def test_confianca_visual_dom_erro():
    assert confianca_visual({"erro_visivel_no_dom": True}) >= 0.8
