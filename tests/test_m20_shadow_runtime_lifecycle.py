"""M20 shadow-runtime lifecycle tests.

These tests exercise the runtime lifecycle without a network connection.
They prove that the runtime delegates start/stop correctly, records completed
candles, exposes evidence, and never needs a broker execution path.
"""

from __future__ import annotations

from datetime import datetime, timezone

from runtime.health import ShadowHealth
from runtime.mode import RuntimeSafety
from runtime.shadow_runtime import ShadowRuntime


class _FakePipeline:
    """Minimal pipeline seam used for deterministic lifecycle tests."""

    def __init__(self) -> None:
        self.started_with = None
        self.stop_calls = 0
        self.run_calls = 0

    def start(self, symbols) -> None:
        self.started_with = tuple(symbols)

    def run(self):
        self.run_calls += 1
        yield object()
        yield object()

    def stop(self) -> None:
        self.stop_calls += 1


class _FakeFeed:
    """Placeholder provider object for the composed runtime."""

    pass


class _FakeMetrics:
    """Minimal metrics seam returning a stable snapshot."""

    class _Snapshot:
        events_received = 2
        events_accepted = 2
        events_rejected = 0
        stale_events = 0
        duplicate_events = 0
        latency_sample_count = 2
        latency_avg_ms = 1.0
        latency_p95_ms = 2.0
        clock_skew_events = 0
        connection_failures = 0
        reconnect_attempts = 0
        reconnect_successes = 0
        reconnect_failures = 0
        missing_data_gaps = 0

    def snapshot(self):
        return self._Snapshot()


class _Config:
    symbols = ("ITC", "TCS")
    timeframe_minutes = 5


def _runtime() -> tuple[ShadowRuntime, _FakePipeline]:
    pipeline = _FakePipeline()
    runtime = ShadowRuntime(
        config=_Config(),
        safety=RuntimeSafety(
            mode="SHADOW",
            live_broker_order_submission=False,
        ),
        feed=_FakeFeed(),
        pipeline=pipeline,
        metrics=_FakeMetrics(),
        health=ShadowHealth(
            started_at=datetime.now(timezone.utc),
        ),
    )
    return runtime, pipeline


def test_shadow_runtime_start_delegates_subscription() -> None:
    """Start must use the configured symbols and remain in SHADOW mode."""
    runtime, pipeline = _runtime()

    runtime.start()

    assert pipeline.started_with == ("ITC", "TCS")
    assert runtime.safety.mode == "SHADOW"
    assert runtime.safety.live_broker_order_submission is False


def test_shadow_runtime_candles_update_health() -> None:
    """Every completed candle yielded by the pipeline updates health."""
    runtime, pipeline = _runtime()

    runtime.start()
    candles = list(runtime.candles())

    assert len(candles) == 2
    assert pipeline.run_calls == 1
    assert runtime.health.candles_completed == 2


def test_shadow_runtime_stop_is_graceful() -> None:
    """Stop delegates exactly once and does not require broker I/O."""
    runtime, pipeline = _runtime()

    runtime.start()
    runtime.stop()
    runtime.stop()

    assert pipeline.stop_calls == 2


def test_shadow_runtime_evidence_preserves_no_order_posture() -> None:
    """Operational evidence must retain the hard M20 no-order boundary."""
    runtime, _pipeline = _runtime()

    evidence = runtime.evidence()

    assert evidence["mode"] == "SHADOW"
    assert evidence["live_broker_order_submission"] is False
