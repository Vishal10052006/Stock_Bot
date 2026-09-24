from backtesting.fills import FillConfig, FillModel
from trading.strategy.models import StrategyDirection


def test_long_fill_has_adverse_slippage() -> None:
    result = FillModel(
        FillConfig(slippage_bps=10.0)
    ).fill(
        price=100.0,
        quantity=10.0,
        direction=StrategyDirection.LONG,
    )

    assert result.fill_price == 100.1
    assert result.slippage_cost == 1.0


def test_short_fill_has_adverse_slippage() -> None:
    result = FillModel(
        FillConfig(slippage_bps=10.0)
    ).fill(
        price=100.0,
        quantity=10.0,
        direction=StrategyDirection.SHORT,
    )

    assert result.fill_price == 99.9
    assert result.slippage_cost == 1.0


import pytest

@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_fill_config_rejects_non_finite_slippage(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        FillConfig(slippage_bps=value)


@pytest.mark.parametrize(
    ("price", "quantity"),
    [(float("nan"), 10.0), (float("inf"), 10.0), (100.0, float("nan"))],
)
def test_fill_model_rejects_non_finite_inputs(price: float, quantity: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        FillModel().fill(
            price=price,
            quantity=quantity,
            direction=StrategyDirection.LONG,
        )
