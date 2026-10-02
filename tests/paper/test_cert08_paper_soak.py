"""Tests for the CERT-08 paper-soak evidence harness."""

import json
from pathlib import Path

import pytest

from scripts.cert08_paper_soak import build_cert08_evidence


def _write_session(
    root: Path,
    *,
    start: str,
    end: str,
    broker_orders: int = 0,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    summary = {
        "session_id": "CERT08-TEST",
        "initial_equity": 100_000.0,
        "final_equity": 100_000.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "gross_exposure": 0.0,
        "open_positions": 0,
        "completed_trades": 0,
        "live_broker_orders": broker_orders,
        "account_ledger": str(root / "account_ledger.jsonl"),
    }
    canonical = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    import hashlib
    summary["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    (root / "account_summary.json").write_text(
        json.dumps(summary, sort_keys=True),
        encoding="utf-8",
    )
    rows = [
        {
            "timestamp": start,
            "equity": 100_000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "gross_exposure": 0.0,
            "open_positions": 0,
        },
        {
            "timestamp": end,
            "equity": 100_000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "gross_exposure": 0.0,
            "open_positions": 0,
        },
    ]
    (root / "account_ledger.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_cert08_marks_duration_as_partial_when_requirement_is_not_met(tmp_path: Path):
    session = tmp_path / "session"
    _write_session(
        session,
        start="2026-10-02T09:15:00+05:30",
        end="2026-10-02T12:15:00+05:30",
    )

    evidence = build_cert08_evidence(session, required_hours=6)

    assert evidence["status"] == "PARTIAL"
    assert evidence["validator_status"] == "PASS"
    assert evidence["live_broker_orders"] == 0


def test_cert08_passes_only_when_observed_duration_meets_requirement(tmp_path: Path):
    session = tmp_path / "session"
    _write_session(
        session,
        start="2026-10-02T09:15:00+05:30",
        end="2026-10-02T15:15:00+05:30",
    )

    evidence = build_cert08_evidence(session, required_hours=6)

    assert evidence["status"] == "PASS"
    assert evidence["observed_duration_seconds"] == 21_600.0


def test_cert08_rejects_nonzero_live_broker_orders(tmp_path: Path):
    session = tmp_path / "session"
    _write_session(
        session,
        start="2026-10-02T09:15:00+05:30",
        end="2026-10-02T15:15:00+05:30",
        broker_orders=1,
    )

    with pytest.raises(ValueError, match="live broker orders"):
        build_cert08_evidence(session, required_hours=6)


def test_cert08_aggregates_multiple_sessions_by_observed_duration(tmp_path):
    """Multiple market sessions can satisfy a cumulative soak requirement."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_session(
        first,
        start="2026-10-02T09:15:00+05:30",
        end="2026-10-02T12:15:00+05:30",
    )
    _write_session(
        second,
        start="2026-10-05T09:15:00+05:30",
        end="2026-10-05T12:15:00+05:30",
    )

    evidence = build_cert08_evidence(
        [first, second],
        required_hours=6,
    )

    assert evidence["status"] == "PASS"
    assert evidence["session_count"] == 2
    assert evidence["observed_duration_seconds"] == 21_600.0


def test_cert08_records_cadence_violation_as_partial(tmp_path: Path):
    """Optional gap validation never upgrades missing observations."""
    session = tmp_path / "session"
    _write_session(
        session,
        start="2026-10-02T09:15:00+05:30",
        end="2026-10-02T15:15:00+05:30",
    )

    evidence = build_cert08_evidence(
        session,
        required_hours=6,
        max_gap_minutes=10,
    )

    assert evidence["status"] == "PARTIAL"
    assert evidence["cadence_status"] == "PARTIAL"
    assert evidence["sessions"][0]["gap_violation"] is True
