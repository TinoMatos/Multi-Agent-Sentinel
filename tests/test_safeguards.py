import pytest

from guards.safeguards import BudgetExceeded, Limits, check


def test_check_dentro_dos_limites():
    check(iteracao=1, tokens_gastos=100, limits=Limits(max_iterations=5, token_budget=1000))


def test_check_estoura_iteracoes():
    with pytest.raises(BudgetExceeded, match="max_iterations"):
        check(iteracao=6, tokens_gastos=0, limits=Limits(max_iterations=5, token_budget=1000))


def test_check_estoura_tokens():
    with pytest.raises(BudgetExceeded, match="token_budget"):
        check(iteracao=1, tokens_gastos=2000, limits=Limits(max_iterations=5, token_budget=1000))
