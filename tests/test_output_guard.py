from guards.output_guard import sanitize


def test_redige_email():
    assert "[EMAIL_REDACTED]" in sanitize("contato: joao@acme.com.br")


def test_redige_cpf():
    assert "[CPF_REDACTED]" in sanitize("doc 123.456.789-00 do cliente")


def test_redige_api_key():
    out = sanitize("api_key: sk-or-abc123def456")
    assert "sk-or-abc123def456" not in out
    assert "REDACTED" in out


def test_preserva_texto_sem_segredos():
    texto = "Tudo certo, sem dados sensiveis aqui."
    assert sanitize(texto) == texto


def test_redige_token_inline():
    out = sanitize("Authorization token=ghp_abcdef123456")
    assert "ghp_abcdef123456" not in out
