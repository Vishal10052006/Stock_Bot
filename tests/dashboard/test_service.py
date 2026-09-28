from __future__ import annotations

from datetime import datetime, timezone

from dashboard.contracts import DashboardConfig
from dashboard.service import DashboardService
from monitoring.journal import MonitoringEvent, MonitoringJournal


def test_dashboard_exposes_latest_causal_market_context(tmp_path):
    journal = MonitoringJournal(tmp_path / "monitoring.jsonl")
    timestamp = datetime(2026, 9, 20, 9, 15, tzinfo=timezone.utc)
    event = MonitoringEvent.create(
        event_type="MARKET_CONTEXT",
        source="market_bot",
        timestamp=timestamp,
        correlation_id="market:test",
        payload={
            "timestamp": timestamp.isoformat(),
            "benchmark": "NIFTY",
            "regime": "TREND",
            "trend_state": "UP",
            "availability": "AVAILABLE",
            "provenance": {
                "causal_boundary": "information_available_at_context_timestamp"
            },
        },
    )
    journal.append(event)

    service = DashboardService(
        DashboardConfig(journal_path=str(journal.path)),
        journal=journal,
    )

    market = service.market()

    assert market["observed"] is True
    assert market["timestamp"] == timestamp.isoformat()
    assert market["context"]["benchmark"] == "NIFTY"
    assert market["context"]["provenance"]["causal_boundary"] == (
        "information_available_at_context_timestamp"
    )
