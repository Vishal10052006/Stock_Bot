"""Tests for the observation-only funds/margin contract."""

from datetime import datetime, timezone

import pytest

from execution.funds_margin import FundsMarginSnapshot


def snapshot() -> FundsMarginSnapshot:
    return FundsMarginSnapshot(
        timestamp=datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc),
        available_cash=75_000.0,
        used_margin=20_000.0,
        available_margin=80_000.0,
        total_margin=100_000.0,
        source="paper",
    )


def test_funds_margin_snapshot_exposes_capacity_and_utilization():
    value = snapshot()

    assert value.margin_utilization == 0.2
    assert value.evidence()["live_broker_order_submission"] is False


def test_funds_margin_snapshot_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        FundsMarginSnapshot(
            timestamp=datetime(2026, 9, 1, 9, 15),
            available_cash=100_000.0,
        )


def test_funds_margin_snapshot_rejects_negative_values():
    with pytest.raises(ValueError, match="non-negative"):
        FundsMarginSnapshot(
            timestamp=datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc),
            available_cash=-1.0,
        )


def test_funds_margin_snapshot_rejects_inconsistent_capacity():
    with pytest.raises(ValueError, match="available_margin"):
        FundsMarginSnapshot(
            timestamp=datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc),
            available_cash=100_000.0,
            available_margin=101.0,
            total_margin=100.0,
        )


def test_funds_margin_evidence_contains_no_credentials():
    evidence = snapshot().evidence()

    assert "access_token" not in str(evidence).lower()
    assert "secret" not in str(evidence).lower()
