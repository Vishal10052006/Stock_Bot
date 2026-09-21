import pandas as pd

from backtesting.metrics import calculate_metrics
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _trade(pnl: float) -> TradeOutcome:
    return TradeOutcome(
        symbol="ITC",
        direction=StrategyDirection.LONG,
        entry_time=pd.Timestamp("2026-01-01 09:15:00+05:30"),
        exit_time=pd.Timestamp("2026-01-01 09:30:00+05:30"),
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        gross_pnl=pnl,
        fees=0.0,
        slippage_cost=0.0,
        net_pnl=pnl,
        holding_minutes=15.0,
        mae=min(pnl, 0.0),
        mfe=max(pnl, 0.0),
    )


def test_empty_metrics_are_zero() -> None:
    metrics = calculate_metrics(())

    assert metrics.trade_count == 0
    assert metrics.net_pnl == 0.0


def test_metrics_capture_wins_and_losses() -> None:
    metrics = calculate_metrics(
        (
            _trade(10.0),
            _trade(-5.0),
        )
    )

    assert metrics.trade_count == 2
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 1
    assert metrics.net_pnl == 5.0
    assert metrics.win_rate == 0.5
    assert metrics.profit_factor == 2.0
    assert metrics.maximum_drawdown == 5.0
