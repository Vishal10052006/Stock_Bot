from datetime import datetime, timezone

import pytest

from monitoring.journal import MonitoringEvent, MonitoringJournal


def _event() -> MonitoringEvent:
    return MonitoringEvent.create(
        event_type="SYSTEM_METRIC",
        source="market_bot",
        timestamp=datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc),
        severity="INFO",
        correlation_id="run-1",
        payload={"error_rate": 0.02, "events": 100},
    )


def test_monitoring_event_has_deterministic_identity() -> None:
    first = _event()
    second = _event()

    assert first.event_id == second.event_id
    assert first.fingerprint == second.fingerprint


def test_journal_round_trip_and_replay(tmp_path) -> None:
    journal = MonitoringJournal(tmp_path / "monitoring.jsonl")
    event = _event()

    journal.append(event)

    assert journal.count() == 1
    assert journal.events() == (event,)
    assert journal.replay(source="market_bot") == (event,)
    assert journal.replay(source="analysis_bot") == ()


def test_journal_rejects_duplicate_event_identity(tmp_path) -> None:
    journal = MonitoringJournal(tmp_path / "monitoring.jsonl")
    event = _event()

    journal.append(event)

    with pytest.raises(ValueError, match="event_id already exists"):
        journal.append(event)


def test_journal_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MonitoringEvent.create(
            event_type="HEALTH",
            source="test",
            timestamp="2026-09-24T14:00:00",
            payload={},
        )


def test_journal_rejects_non_json_payload() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        MonitoringEvent.create(
            event_type="HEALTH",
            source="test",
            payload={"bad": object()},
        )


def test_journal_reader_detects_corruption(tmp_path) -> None:
    path = tmp_path / "monitoring.jsonl"
    path.write_text('{"event_id":"broken"}\n', encoding="utf-8")

    journal = MonitoringJournal(path)

    with pytest.raises(ValueError, match="invalid monitoring JSONL"):
        journal.events()
