"""Exposure and projection tests."""

from __future__ import annotations

import pandas as pd

from portfolio.contracts import PortfolioPosition, PortfolioSnapshot, TradeIntent
from portfolio.exposure import (
    projected_snapshot,
    sector_exposure_fraction,
    symbol_exposure_fraction,
)


def snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        pd.Timestamp("2026-01-01", tz="Asia/Kolkata"),
        100000.0,
        (
            PortfolioPosition("INFY", 10, 1500, "IT"),
            PortfolioPosition("RELIANCE", 10, 2500, "ENERGY"),
        ),
    )


def test_gross_exposure_uses_absolute_long_and_short_values() -> None:
    state = PortfolioSnapshot(
        pd.Timestamp("2026-01-01", tz="Asia/Kolkata"),
        100000.0,
        (PortfolioPosition("INFY", -10, 1500, "IT"),),
    )
    assert state.gross_exposure == 15000
    assert state.gross_exposure_fraction == 0.15


def test_buy_increases_existing_position() -> None:
    projected = projected_snapshot(snapshot(), TradeIntent("INFY", 5, 1500, "BUY", "IT"))
    assert projected.positions[0].quantity == 15


def test_sell_decreases_existing_position() -> None:
    projected = projected_snapshot(snapshot(), TradeIntent("INFY", 5, 1500, "SELL", "IT"))
    assert projected.positions[0].quantity == 5


def test_flattening_position_removes_symbol() -> None:
    projected = projected_snapshot(
        snapshot(),
        TradeIntent("INFY", 10, 1500, "SELL", "IT"),
    )
    assert all(position.symbol != "INFY" for position in projected.positions)


def test_symbol_and_sector_exposure_are_fractional() -> None:
    state = snapshot()
    assert symbol_exposure_fraction(state, "INFY") == 0.15
    assert sector_exposure_fraction(state, "IT") == 0.15
