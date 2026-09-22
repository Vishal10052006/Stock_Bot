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
