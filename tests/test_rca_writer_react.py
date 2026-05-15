import pytest

from agents import rca_writer


def _planner_scriptado(passos):
    it = iter(passos)
    def _p(_estado):
        return next(it)
    return _p


def test_loop_react_coleta_evidencias_e_finaliza():
    passos = [
        {
            "raciocinio": "sei o cliente; falta evidencia de commit; vou registrar.",
            "proxima_acao": "CHAMAR_FERRAMENTA",
            "nome_ferramenta": "registrar_evidencia",
            "argumentos_ferramenta": {"tipo": "commit", "ref": "a1b2", "nota": "regressao"},
            "criterio_sucesso": "evidencia registrada",
        },
        {
            "raciocinio": "tenho 1 evidencia; suficiente para concluir.",
            "proxima_acao": "FINALIZAR",
            "argumentos_ferramenta": {"conclusao": "Deploy ruim.", "confianca": 0.9},
            "criterio_sucesso": "RCA finalizado",
        },
    ]
    estado = rca_writer.executar_react(
        cliente="Acme", pergunta="por que caiu?",
        planner=_planner_scriptado(passos),
    )
    assert estado["finalizado"]
    assert estado["iteracao"] == 2
    assert len(estado["evidencias"]) == 1
    assert "Deploy ruim." in estado["markdown"]
    assert "90%" in estado["markdown"]


def test_passo_sem_raciocinio_falha():
    passos = [{"proxima_acao": "FINALIZAR", "criterio_sucesso": "x"}]
    with pytest.raises(ValueError, match="raciocinio"):
        rca_writer.executar_react("Acme", "?", _planner_scriptado(passos))


def test_chamar_ferramenta_sem_nome_falha():
    passos = [{
        "raciocinio": "r", "proxima_acao": "CHAMAR_FERRAMENTA",
        "criterio_sucesso": "c",
    }]
    with pytest.raises(ValueError, match="nome_ferramenta"):
        rca_writer.executar_react("Acme", "?", _planner_scriptado(passos))


def test_perguntar_usuario_interrompe_loop():
    passos = [{
        "raciocinio": "preciso de mais contexto",
        "proxima_acao": "PERGUNTAR_USUARIO",
        "pergunta": "qual o ticket?",
        "criterio_sucesso": "obter ticket",
    }]
    estado = rca_writer.executar_react("Acme", "?", _planner_scriptado(passos))
    assert not estado["finalizado"]
    assert estado["pergunta_pendente"] == "qual o ticket?"


def test_max_iteracoes_para_loop_infinito():
    def planner_infinito(_):
        return {
            "raciocinio": "registrando mais uma",
            "proxima_acao": "CHAMAR_FERRAMENTA",
            "nome_ferramenta": "registrar_evidencia",
            "argumentos_ferramenta": {"tipo": "log", "ref": "x", "nota": "y"},
            "criterio_sucesso": "c",
        }
    estado = rca_writer.executar_react("Acme", "?", planner_infinito, max_iteracoes=3)
    assert not estado["finalizado"]
    assert estado["iteracao"] == 3
    assert len(estado["evidencias"]) == 3
