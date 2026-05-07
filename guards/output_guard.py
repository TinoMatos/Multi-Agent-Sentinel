"""Output Guard: sanitiza relatorio final antes de exibir ao usuario.

Stub da Fase 2 — entra cedo de proposito (ver README secao 5).
"""
import re

_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"), r"\1: [REDACTED]"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL_REDACTED]"),
]


def sanitize(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text
