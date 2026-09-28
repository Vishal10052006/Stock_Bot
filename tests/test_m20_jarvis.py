from datetime import datetime, timezone
from runtime.jarvis import JarvisLifecycle, LifecyclePhase
from runtime.mode import RuntimeSafety


def _lifecycle(hooks=None):
    return JarvisLifecycle(
        safety=RuntimeSafety(mode="SHADOW", live_broker_order_submission=False),
        hooks=hooks or {},
    )


def test_daily_lifecycle_runs_in_order_and_fails_closed():
    calls = []
    hooks = {
        phase: (lambda phase=phase: calls.append(phase.value) or {"phase": phase.value})
        for phase in LifecyclePhase
    }
    lifecycle = _lifecycle(hooks)
    results = lifecycle.run_daily()
    assert [item.phase for item in results] == list(LifecyclePhase)
    assert calls == [item.value for item in LifecyclePhase]
    assert all(item.evidence["live_broker_order_submission"] is False for item in results)


def test_failed_phase_stops_remaining_sequence():
    def broken():
        raise RuntimeError("boom")

    lifecycle = _lifecycle({LifecyclePhase.BOOT: broken, LifecyclePhase.PRE_OPEN: lambda: {}})
    results = lifecycle.run_daily()
    assert results[0].status == "FAILED_CLOSED"
    assert len(results) == 1
    assert lifecycle.dashboard()["failed_closed_count"] == 1


def test_phase_resolution_uses_ist():
    lifecycle = _lifecycle()
    at_open = datetime(2026, 9, 26, 9, 30, tzinfo=timezone.utc)
    assert lifecycle.phase_for(at_open) is LifecyclePhase.MARKET_ACTIVE
