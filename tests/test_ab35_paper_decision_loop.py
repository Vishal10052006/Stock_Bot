"""AB-35 paper decision-loop coverage."""
from __future__ import annotations

import pandas as pd

from paper.runtime import PaperOrderStatus
from trading.paper.decision_loop import PaperDecisionLoop


def _row(timestamp: str, direction: str = "LONG") -> dict:
    if direction == "LONG":
        return {
            "timestamp": timestamp,
            "symbol": "RELIANCE",
            "regime": "TREND_UP",
            "regime_probability": 0.9,
            "vwap_distance_pct": 1.0,
            "rvol_20": 1.5,
            "higher_high": True,
            "higher_low": True,
            "lower_low": False,
            "lower_high": False,
            "close": 100.0,
        }
    return {
        "timestamp": timestamp,
        "symbol": "RELIANCE",
        "regime": "RANGE",
        "regime_probability": 0.9,
        "vwap_distance_pct": 0.0,
        "rvol_20": 0.5,
        "higher_high": False,
        "higher_low": False,
        "lower_low": False,
        "lower_high": False,
        "close": 100.0,
    }


def test_ab35_runs_strategy_risk_authorization_and_paper_fill() -> None:
    rows = pd.DataFrame(
        [
            _row("2026-09-20 10:25:00+05:30"),
            _row("2026-09-20 10:20:00+05:30", "NO_TRADE"),
        ]
    )

    result = PaperDecisionLoop().run(rows, quantity=2.0)

    assert len(result.steps) == 2
    assert len(result.orders) == 1
    assert result.orders[0].status is PaperOrderStatus.FILLED


def test_ab35_orders_follow_timestamp_order() -> None:
    rows = pd.DataFrame(
        [
            _row("2026-09-20 10:30:00+05:30"),
            _row("2026-09-20 10:15:00+05:30"),
            _row("2026-09-20 10:25:00+05:30"),
        ]
    )

    result = PaperDecisionLoop().run(rows)

    timestamps = [step.strategy.timestamp for step in result.steps]
    assert timestamps == sorted(timestamps)


def test_ab35_disabled_risk_produces_no_orders() -> None:
    rows = pd.DataFrame([_row("2026-09-20 10:25:00+05:30")])

    result = PaperDecisionLoop(risk_enabled=False).run(rows)

    assert len(result.steps) == 1
    assert result.steps[0].authorization.status.value == "BLOCKED"
    assert result.orders == ()
