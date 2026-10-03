from datetime import datetime, timezone
import json

import pytest

from dashboard.server import record_outcome, record_review
from journal.manual_review import ManualOutcomeStatus, ManualReviewJournal, ManualReviewStore
from v1_signal.contracts import V1Signal, V1SignalContract


def _signal(*, valid_until=None) -> V1SignalContract:
    timestamp = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
    return V1SignalContract(
        signal_id="V1-TEST-SERVER",
        timestamp=timestamp,
        symbol="TEST.NS",
        signal=V1Signal.BUY,
        entry=100.0,
        stop_loss=95.0,
        target=110.0,
        risk_reward=2.0,
        confidence=0.8,
        prediction_evidence={"probabilities": {"LONG_SUCCESS": 0.8, "SHORT_SUCCESS": 0.1, "NO_EDGE": 0.1}},
        valid_until=valid_until or datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc),
        technical_evidence=(),
        provenance={"strategy_version": "test"},
    )


def _snapshot(path, signal):
    path.write_text(json.dumps({"v1_signal": signal.as_dict()}), encoding="utf-8")


def test_signal_snapshot_round_trip_revalidates_contract():
    original = _signal()
    restored = V1SignalContract.from_dict(original.as_dict())

    assert restored.signal_id == original.signal_id
    assert restored.symbol == original.symbol
    assert restored.signal is V1Signal.BUY
    assert restored.broker_execution is False
    assert restored.authority == "MANUAL_REAL_MONEY_REVIEW"


def test_dashboard_review_records_exact_snapshot(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _snapshot(snapshot, _signal())
    journal = ManualReviewJournal(ManualReviewStore(tmp_path / "journal.jsonl"))

    review = record_review(
        snapshot_path=snapshot,
        journal=journal,
        action="ACCEPT",
        reviewed_at=datetime(2026, 10, 3, 9, 5, tzinfo=timezone.utc),
        review_note="Reviewed canonical evidence.",
    )

    assert review.signal_id == "V1-TEST-SERVER"
    assert review.action.value == "ACCEPT"
    assert journal.reviews()[0] == review


def test_dashboard_rejects_accepting_expired_signal(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _snapshot(
        snapshot,
        _signal(valid_until=datetime(2026, 10, 3, 8, 59, tzinfo=timezone.utc)),
    )
    journal = ManualReviewJournal(ManualReviewStore(tmp_path / "journal.jsonl"))

    with pytest.raises(ValueError, match="expired"):
        record_review(
            snapshot_path=snapshot,
            journal=journal,
            action="ACCEPT",
            reviewed_at=datetime(2026, 10, 3, 9, 5, tzinfo=timezone.utc),
            review_note="Too late.",
        )


def test_dashboard_outcome_is_operator_supplied_and_single_per_review(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _snapshot(snapshot, _signal())
    journal = ManualReviewJournal(ManualReviewStore(tmp_path / "journal.jsonl"))
    review = record_review(
        snapshot_path=snapshot,
        journal=journal,
        action="ACCEPT",
        reviewed_at=datetime(2026, 10, 3, 9, 5, tzinfo=timezone.utc),
        review_note="Manual review.",
    )

    outcome = record_outcome(
        journal=journal,
        payload={
            "review_id": review.review_id,
            "observed_at": "2026-10-03T12:00:00+00:00",
            "status": "CLOSED",
            "execution_timestamp": "2026-10-03T09:06:00+00:00",
            "entry_price": 100.5,
            "exit_timestamp": "2026-10-03T11:00:00+00:00",
            "exit_price": 109.0,
            "quantity": 2,
            "fees": 2,
            "slippage_cost": 1,
            "net_pnl": 15,
            "note": "Entered and exited manually.",
        },
    )

    assert outcome.status is ManualOutcomeStatus.CLOSED
    assert journal.outcome_for_review(review.review_id) == outcome

    with pytest.raises(ValueError, match="already exists"):
        record_outcome(
            journal=journal,
            payload={
                "review_id": review.review_id,
                "observed_at": "2026-10-03T12:01:00+00:00",
                "status": "NOT_EXECUTED",
            },
        )
