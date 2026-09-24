"""Contract tests for the deterministic portfolio boundary."""

from __future__ import annotations

import pandas as pd
import pytest

from portfolio.contracts import (
    PortfolioLimits,
    PortfolioPosition,
    PortfolioSnapshot,
    TradeIntent,
)


def test_position_normalizes_symbol_and_computes_signed_value() -> None:
    position = PortfolioPosition(" infy ", -10, 1500.0, "IT")
    assert position.symbol == "INFY"
    assert position.market_value == -15000.0


def test_snapshot_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PortfolioSnapshot(pd.Timestamp("2026-01-01"), 100000.0)


def test_snapshot_rejects_duplicate_symbols() -> None:
    positions = (
        PortfolioPosition("INFY", 10, 1500),
        PortfolioPosition("INFY", 5, 1500),
    )
    with pytest.raises(ValueError, match="duplicate symbols"):
        PortfolioSnapshot(pd.Timestamp("2026-01-01", tz="Asia/Kolkata"), 100000, positions)


def test_trade_intent_rejects_invalid_side() -> None:
    with pytest.raises(ValueError, match="BUY or SELL"):
        TradeIntent("INFY", 10, 1500, "HOLD")


def test_limits_reject_fraction_above_one() -> None:
    with pytest.raises(ValueError, match="in (0, 1]"):
        PortfolioLimits(max_gross_exposure_fraction=1.1)
