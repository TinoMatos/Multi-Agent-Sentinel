"""Safeguards: limites duros que a Triagem consulta antes de cada iteracao."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Limits:
    max_iterations: int = int(os.getenv("SENTINEL_MAX_ITERATIONS", "8"))
    token_budget: int = int(os.getenv("SENTINEL_TOKEN_BUDGET", "50000"))


class BudgetExceeded(RuntimeError):
    pass


def check(iteracao: int, tokens_gastos: int, limits: Limits | None = None) -> None:
    limits = limits or Limits()
    if iteracao > limits.max_iterations:
        raise BudgetExceeded(f"max_iterations={limits.max_iterations} excedido")
    if tokens_gastos > limits.token_budget:
        raise BudgetExceeded(f"token_budget={limits.token_budget} excedido")
