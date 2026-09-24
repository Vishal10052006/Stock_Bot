from backtesting.costs import CostConfig, TransactionCostModel


def test_zero_cost_model() -> None:
    result = TransactionCostModel().calculate(
        price=100.0,
        quantity=10.0,
    )

    assert result.notional == 1000.0
    assert result.total == 0.0


def test_cost_model_is_deterministic() -> None:
    model = TransactionCostModel(
        CostConfig(
            brokerage_bps=10.0,
            exchange_txn_bps=5.0,
        )
    )

    result = model.calculate(
        price=100.0,
        quantity=10.0,
    )

    assert result.total == 1.5


import pytest

@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_cost_config_rejects_non_finite_rates(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        CostConfig(brokerage_bps=value)


@pytest.mark.parametrize(
    ("price", "quantity"),
    [(float("nan"), 10.0), (float("inf"), 10.0), (100.0, float("nan"))],
)
def test_cost_model_rejects_non_finite_inputs(price: float, quantity: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        TransactionCostModel().calculate(price=price, quantity=quantity)
