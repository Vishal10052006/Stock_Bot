"""Tests for M20 shadow session evidence journaling."""

from datetime import datetime, timezone

from runtime.shadow_session import ShadowSessionJournal


def test_shadow_session_journal_records_correlated_lifecycle(tmp_path) -> None:
    journal = ShadowSessionJournal.open(tmp_path / "shadow.jsonl", session_id="m20-test")

    journal.start(symbols=("ITC", "TCS"))
    journal.candle(
        symbol="ITC",
        timestamp=datetime(2026, 9, 28, 9, 15, tzinfo=timezone.utc),
    )
    journal.stop(
        evidence={
            "candles_completed": 1,
            "mode": "SHADOW",
        }
    )

    events = journal.events()

    assert len(events) == 3
    assert all(event.correlation_id == "m20-test" for event in events)
    assert events[0].event_type == "SHADOW_SESSION_STARTED"
    assert events[1].event_type == "SHADOW_CANDLE_COMPLETED"
    assert events[2].event_type == "SHADOW_SESSION_STOPPED"
    assert journal.evidence()["event_count"] == 3
    assert journal.evidence()["live_broker_order_submission"] is False


def test_shadow_session_journal_replays_only_current_session(tmp_path) -> None:
    path = tmp_path / "shadow.jsonl"

    first = ShadowSessionJournal.open(path, session_id="first")
    second = ShadowSessionJournal.open(path, session_id="second")

    first.start(symbols=("ITC",))
    second.start(symbols=("TCS",))

    assert len(first.events()) == 1
    assert len(second.events()) == 1
    assert first.events()[0].correlation_id == "first"
    assert second.events()[0].correlation_id == "second"
