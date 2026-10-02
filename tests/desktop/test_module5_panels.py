from __future__ import annotations

from datetime import datetime, timedelta, timezone

from desktop.application import DesktopApplication
from desktop.read_models import (
    ReplayState,
    build_explanation,
    build_market_dashboard,
    build_prediction_panel,
    build_research_panel,
    build_screen_panel,
    build_timeline,
)


def test_d01_dashboard_is_deterministic_and_live_locked() -> None:
    now = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    market = {"symbol": "RELIANCE", "timeframe": "5m", "close": 2500.0, "timestamp": now.isoformat()}
    state = build_market_dashboard(market=market, now=now)
    assert state.symbol == "RELIANCE"
    assert state.price == 2500.0
    assert state.live_execution_state == "LOCKED"
    assert state.as_dict() == state.as_dict()


def test_d02_prediction_accepts_canonical_probabilities() -> None:
    prediction = {
        "timestamp": datetime(2026, 10, 2, 10, tzinfo=timezone.utc),
        "symbol": "RELIANCE",
        "long_probability": 0.6,
        "short_probability": 0.2,
        "no_edge_probability": 0.2,
        "model_version": "m1",
    }
    state = build_prediction_panel(prediction)
    assert state.status == "VALID"
    assert state.long_success == 0.6


def test_d02_prediction_rejects_malformed_probability_payload() -> None:
    state = build_prediction_panel({"long_probability": 0.9, "short_probability": 0.9, "no_edge_probability": 0.0})
    assert state.status == "INVALID"


def test_d03_explanation_never_invents_missing_layers() -> None:
    state = build_explanation({"analysis": {"timestamp": datetime(2026, 10, 2, 10, tzinfo=timezone.utc), "symbol": "RELIANCE"}})
    assert [item.source for item in state.items] == ["market"]


def test_d04_future_research_is_not_exposed() -> None:
    decision = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    future = decision + timedelta(minutes=1)
    state = build_research_panel(
        [{"id": "future", "title": "Future", "source": "x", "available_at": future}]
        , decision_timestamp=decision
    )
    assert state.items == ()
    assert state.status == "FUTURE_EVIDENCE_REJECTED"


def test_d05_missing_screen_is_fail_closed() -> None:
    state = build_screen_panel()
    assert state.capture_status == "UNAVAILABLE"
    assert state.reconciliation_status == "INVALID"


def test_d06_timeline_is_timestamp_ordered_and_stable() -> None:
    t1 = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    t2 = t1 + timedelta(seconds=1)
    state = build_timeline([
        {"id": "b", "timestamp": t2, "type": "PREDICTION", "source": "prediction"},
        {"id": "a", "timestamp": t1, "type": "MARKET", "source": "market"},
    ])
    assert [event.event_id for event in state.events] == ["a", "b"]
    assert [event.sequence for event in state.events] == [0, 1]


def test_d07_missing_telemetry_is_observable() -> None:
    from desktop.read_models import build_model_telemetry
    assert build_model_telemetry().status == "NO_TELEMETRY"


def test_d08_missing_risk_state_is_not_authorized() -> None:
    from desktop.read_models import build_risk_panel
    assert build_risk_panel().status == "UNKNOWN"
    assert build_risk_panel().authority == "RISK_ENGINE"


def test_d09_missing_paper_runtime_is_safe() -> None:
    from desktop.read_models import build_paper_account
    state = build_paper_account()
    assert state.execution_state == "IDLE"
    assert state.positions == ()


def test_d10_replay_is_deterministic_and_isolated() -> None:
    events = [
        {"id": "1", "timestamp": datetime(2026, 10, 2, 10, tzinfo=timezone.utc), "type": "MARKET", "source": "market"},
        {"id": "2", "timestamp": datetime(2026, 10, 2, 10, 0, 1, tzinfo=timezone.utc), "type": "PREDICTION", "source": "prediction"},
    ]
    replay = __import__("desktop.read_models", fromlist=["start_replay"]).start_replay("s1", events)
    assert replay.live_mutation is False
    assert replay.step().cursor == 1
    assert replay.step().step().status == "COMPLETE"


def test_d01_to_d10_application_snapshot_is_composed() -> None:
    app = DesktopApplication()
    snapshot = app.snapshot()
    assert tuple(snapshot.views) == (
        "market", "prediction", "explanation", "research", "screen",
        "timeline", "telemetry", "risk", "paper", "replay"
    )
    assert snapshot.authority == "OBSERVATION_ONLY"
    assert snapshot.views["market"]["live_execution_state"] == "LOCKED"
