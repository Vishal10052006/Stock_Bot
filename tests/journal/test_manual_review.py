"""Focused tests for the V1 human-review evidence journal."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from journal.manual_review import (
    ManualOutcomeRecord,
    ManualOutcomeStatus,
    ManualReviewAction,
    ManualReviewJournal,
    ManualReviewStore,
)
from v1_signal.contracts import V1Signal, V1SignalContract


def _signal() -> V1SignalContract:
    ts = datetime(2026, 10, 3, 9, 15, tzinfo=timezone.utc)
    return V1SignalContract(
        signal_id="V1-TEST-001",
        timestamp=ts,
        symbol="RELIANCE",
        signal=V1Signal.BUY,
        entry=2500.0,
        stop_loss=2475.0,
        target=2550.0,
        risk_reward=2.0,
        confidence=0.72,
        prediction_evidence={
            "probabilities": {
                "LONG_SUCCESS": 0.72,
                "SHORT_SUCCESS": 0.08,
                "NO_EDGE": 0.20,
            },
            "model_version": "test-model",
        },
        valid_until=datetime(2026, 10, 3, 9, 20, tzinfo=timezone.utc),
        supporting_factors=("trend aligned",),
        contradicting_factors=("news uncertainty",),
        risk_conditions=("risk approved",),
        provenance={"strategy_version": "test-strategy"},
    )


def test_review_captures_exact_signal_and_human_action(tmp_path) -> None:
    journal = ManualReviewJournal(ManualReviewStore(tmp_path / "manual_review.jsonl"))
    signal = _signal()

    record = journal.record_review(
        signal,
        action=ManualReviewAction.ACCEPT,
        reviewed_at=datetime(2026, 10, 3, 9, 16, tzinfo=timezone.utc),
        review_note="Human accepted the setup for manual consideration.",
    )

    assert record.signal_id == signal.signal_id
    assert record.signal_fingerprint == signal.as_dict()["fingerprint"]
    assert record.action is ManualReviewAction.ACCEPT
    assert record.entry == 2500.0
    assert record.risk_reward == 2.0
    assert record.prediction_evidence["probabilities"]["LONG_SUCCESS"] == 0.72


def test_review_round_trip_and_append_only_duplicate_protection(tmp_path) -> None:
    store = ManualReviewStore(tmp_path / "manual_review.jsonl")
    journal = ManualReviewJournal(store)
    record = journal.record_review(
        _signal(),
        action=ManualReviewAction.REJECT,
        reviewed_at=datetime(2026, 10, 3, 9, 16, tzinfo=timezone.utc),
        review_note="Rejected after human review.",
    )

    restored = store.reviews()[0]
    assert restored == record

    with pytest.raises(ValueError, match="duplicate"):
        store.append(record)


def test_outcome_requires_explicit_observation_and_links_to_review(tmp_path) -> None:
    store = ManualReviewStore(tmp_path / "manual_review.jsonl")
    journal = ManualReviewJournal(store)
    review = journal.record_review(
        _signal(),
        action=ManualReviewAction.ACCEPT,
        reviewed_at=datetime(2026, 10, 3, 9, 16, tzinfo=timezone.utc),
    )

    outcome = ManualOutcomeRecord(
        outcome_id="OUT-TEST-001",
        review_id=review.review_id,
        signal_id=review.signal_id,
        observed_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
        status=ManualOutcomeStatus.CLOSED,
        execution_timestamp=datetime(2026, 10, 3, 9, 17, tzinfo=timezone.utc),
        entry_price=2501.0,
        exit_timestamp=datetime(2026, 10, 3, 11, 45, tzinfo=timezone.utc),
        exit_price=2540.0,
        quantity=2.0,
        fees=10.0,
        slippage_cost=2.0,
        net_pnl=66.0,
        note="Entered and exited manually; values supplied by operator.",
    )
    journal.record_outcome(outcome)

    assert journal.outcome_for_review(review.review_id) == outcome


def test_concurrent_outcomes_allow_only_one_append_per_review(tmp_path) -> None:
    store = ManualReviewStore(tmp_path / "manual_review.jsonl")
    journal = ManualReviewJournal(store)
    review = journal.record_review(
        _signal(),
        action=ManualReviewAction.ACCEPT,
        reviewed_at=datetime(2026, 10, 3, 9, 16, tzinfo=timezone.utc),
    )

    def append_outcome(outcome_id: str) -> str:
        outcome = ManualOutcomeRecord(
            outcome_id=outcome_id,
            review_id=review.review_id,
            signal_id=review.signal_id,
            observed_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
            status=ManualOutcomeStatus.NOT_EXECUTED,
            execution_timestamp=None,
            entry_price=None,
            exit_timestamp=None,
            exit_price=None,
            quantity=None,
            fees=None,
            slippage_cost=None,
            net_pnl=None,
        )
        try:
            journal.record_outcome(outcome)
            return "accepted"
        except ValueError as exc:
            assert "already exists" in str(exc)
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(append_outcome, ("OUT-CONCURRENT-1", "OUT-CONCURRENT-2")))

    assert sorted(results) == ["accepted", "rejected"]
    assert len(journal.outcomes()) == 1


def test_executed_outcome_cannot_be_created_without_explicit_execution_facts() -> None:
    with pytest.raises(ValueError, match="executed outcomes require"):
        ManualOutcomeRecord(
            outcome_id="OUT-TEST-002",
            review_id="REV-TEST",
            signal_id="V1-TEST-001",
            observed_at=datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
            status=ManualOutcomeStatus.EXECUTED,
            execution_timestamp=None,
            entry_price=None,
            exit_timestamp=None,
            exit_price=None,
            quantity=None,
            fees=None,
            slippage_cost=None,
            net_pnl=None,
        )


def test_manual_review_journal_has_no_broker_order_surface() -> None:
    source = open("journal/manual_review.py", encoding="utf-8").read()
    forbidden = ("place_order", "modify_order", "cancel_order", "submit_order")
    assert not any(name in source for name in forbidden)
