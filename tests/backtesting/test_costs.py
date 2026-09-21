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
