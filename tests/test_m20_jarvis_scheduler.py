from datetime import datetime, timezone
from runtime.jarvis import JarvisLifecycle
from runtime.jarvis_scheduler import JarvisScheduler, SchedulerConfig
from runtime.mode import RuntimeSafety


def test_scheduler_deduplicates_same_phase():
    now = datetime(2026, 9, 26, 5, 0, tzinfo=timezone.utc)
    lifecycle = JarvisLifecycle(
        safety=RuntimeSafety(mode="SHADOW", live_broker_order_submission=False),
        hooks={},
    )
    scheduler = JarvisScheduler(
        lifecycle,
        config=SchedulerConfig(poll_seconds=1, max_iterations=1),
        clock=lambda: now,
        sleeper=lambda _: None,
    )
    first = scheduler.run_once()
    second = scheduler.run_once()
    assert first.status == "SKIPPED_NO_HOOK"
    assert second["status"] == "ALREADY_RUN"


def test_scheduler_rejects_naive_clock():
    lifecycle = JarvisLifecycle(
        safety=RuntimeSafety(mode="SHADOW", live_broker_order_submission=False),
    )
    scheduler = JarvisScheduler(lifecycle, clock=lambda: datetime(2026, 9, 26, 5))
    try:
        scheduler.run_once()
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive clock must fail")
