from __future__ import annotations

import pandas as pd
import pytest

from multi_stock.portfolio import build_portfolio_context
from portfolio.contracts import PortfolioPosition, PortfolioSnapshot


def test_portfolio_context_is_deterministic_and_observation_only() -> None:
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    snapshot = PortfolioSnapshot(
        as_of=ts,
        equity=100000.0,
        positions=(
            PortfolioPosition("RELIANCE.NS", 10, 2500, "ENERGY"),
            PortfolioPosition("TCS.NS", -5, 4000, "IT"),
        ),
    )

    context = build_portfolio_context(ts, snapshot, cash=50000.0)

    assert context.position_count == 2
    assert context.gross_exposure == 45000.0
    assert context.net_exposure == 5000.0
    assert context.authority == "OBSERVATION_ONLY"
    assert context.as_dict()["authority"] == "OBSERVATION_ONLY"


def test_future_portfolio_snapshot_fails_closed() -> None:
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    future = PortfolioSnapshot(
        as_of=ts + pd.Timedelta(minutes=1),
        equity=100000.0,
    )

    with pytest.raises(ValueError, match="future portfolio snapshot rejected"):
        build_portfolio_context(ts, future)


def test_empty_portfolio_is_valid() -> None:
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    snapshot = PortfolioSnapshot(as_of=ts, equity=100000.0)

    context = build_portfolio_context(ts, snapshot)

    assert context.position_count == 0
    assert context.gross_exposure == 0.0
    assert context.net_exposure == 0.0
