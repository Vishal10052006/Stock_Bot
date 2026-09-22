"""Integration tests for the centralized StrategyEngine boundary."""

from __future__ import annotations

import pandas as pd

from backtesting.engine import HistoricalBacktestEngine
from trading.paper.decision_loop import PaperDecisionLoop
from trading.strategy import StrategyDirection, StrategyEngine, StrategyInput


def strategy_row(
    timestamp: str,
    *,
    symbol: str = "RELIANCE",
    regime: str = "TREND_UP",
    probability: float = 0.90,
) -> dict[str, object]:
    """Create one causal baseline-compatible row."""
    return {
        "timestamp": pd.Timestamp(timestamp, tz="UTC"),
        "symbol": symbol,
        "close": 100.0,
        "regime": regime,
        "regime_probability": probability,
        "vwap_distance_pct": 0.5,
        "rvol_20": 1.4,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }


def test_paper_loop_uses_strategy_engine_output() -> None:
    """Paper decisions must come from the authoritative StrategyEngine."""
    rows = pd.DataFrame([
        strategy_row("2026-09-21 10:00:00"),
        strategy_row("2026-09-21 10:05:00"),
    ])

    result = PaperDecisionLoop().run(rows, quantity=1.0)

    assert result.steps
    assert all(
        step.strategy.strategy_version == "STRAT-v1.0"
        for step in result.steps
    )
    assert result.steps[0].strategy.direction is StrategyDirection.LONG


def test_backtest_uses_strategy_engine_output() -> None:
    """Historical replay must not maintain a second strategy implementation."""
    rows = pd.DataFrame([
        strategy_row("2026-09-21 10:00:00"),
        strategy_row("2026-09-21 10:05:00"),
    ])

    result = HistoricalBacktestEngine().run(rows)

    assert result.steps
    assert all(
        step.strategy.strategy_version == "STRAT-v1.0"
        for step in result.steps
    )
    assert result.steps[0].strategy.direction is StrategyDirection.LONG


def test_strategy_input_is_decision_time_only() -> None:
    """Strategy can operate without future outcome labels."""
    value = StrategyInput(
        timestamp=pd.Timestamp("2026-09-21 10:00:00+00:00"),
        symbol="RELIANCE",
        decision_features={
            "vwap_distance_pct": 0.5,
            "rvol_20": 1.4,
            "higher_high": True,
            "higher_low": True,
            "lower_low": False,
            "lower_high": False,
        },
        regime="TREND_UP",
        regime_probability=0.90,
    )

    decision, _trace = StrategyEngine().decide(value)

    assert decision.direction is StrategyDirection.LONG
    assert not hasattr(decision, "future_return")
