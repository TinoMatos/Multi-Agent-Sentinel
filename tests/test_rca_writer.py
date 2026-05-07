from agents import rca_writer


def test_render_inclui_secoes_obrigatorias():
    md = rca_writer.render_rca(
        cliente="Acme",
        pergunta="por que caiu?",
        conclusao="Deploy ruim.",
        evidencias=[{"tipo": "commit", "ref": "a1b2", "nota": "regressao"}],
        confianca=0.9,
        iteracao=2,
    )
    assert "# RCA — Acme" in md
    assert "## Conclusao" in md
    assert "## Evidencias" in md
    assert "Deploy ruim." in md
    assert "a1b2" in md
    assert "90%" in md


def test_render_inclui_ressalvas_quando_presentes():
    md = rca_writer.render_rca(
        cliente="Acme", pergunta="?", conclusao="x", evidencias=[],
        confianca=0.5, iteracao=1, ressalvas=["evidencias insuficientes"],
    )
    assert "## Ressalvas" in md
    assert "insuficientes" in md


def test_render_omite_ressalvas_quando_vazio():
    md = rca_writer.render_rca(
        cliente="Acme", pergunta="?", conclusao="x", evidencias=[],
        confianca=1.0, iteracao=1,
    )
    assert "Ressalvas" not in md


def test_salvar_grava_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(rca_writer, "REPORTS_DIR", tmp_path)
    path = rca_writer.salvar("# conteudo", "ticket123")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "# conteudo"
    assert "ticket123" in path.name
