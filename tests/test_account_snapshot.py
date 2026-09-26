"""Tests for the provider-neutral account snapshot contract."""

from datetime import datetime, timezone

import pytest

from execution.account import AccountSnapshot


def make_snapshot() -> AccountSnapshot:
    return AccountSnapshot(
        timestamp=datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc),
        equity=100_000.0,
        available_cash=75_000.0,
        gross_exposure=25_000.0,
        open_positions=1,
        realized_pnl=250.0,
        unrealized_pnl=-50.0,
        trades_today=1,
        source="paper",
    )


def test_account_snapshot_validates_and_exposes_net_pnl():
    snapshot = make_snapshot()

    assert snapshot.net_pnl == 200.0
    assert snapshot.source == "paper"
    assert snapshot.evidence()["live_broker_order_submission"] is False


def test_account_snapshot_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        AccountSnapshot(
            timestamp=datetime(2026, 9, 1, 9, 15),
            equity=100_000.0,
            available_cash=100_000.0,
        )


def test_account_snapshot_rejects_invalid_account_values():
    with pytest.raises(ValueError, match="equity must be positive"):
        AccountSnapshot(
            timestamp=datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc),
            equity=0.0,
            available_cash=0.0,
        )

    with pytest.raises(ValueError, match="available_cash"):
        AccountSnapshot(
            timestamp=datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc),
            equity=100_000.0,
            available_cash=-1.0,
        )


def test_account_snapshot_evidence_contains_no_credentials():
    snapshot = make_snapshot()

    evidence = snapshot.evidence()

    assert "access_token" not in str(evidence).lower()
    assert "secret" not in str(evidence).lower()
