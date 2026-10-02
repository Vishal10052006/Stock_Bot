from datetime import timedelta
import threading
import time

import pandas as pd

from screen_observer.contracts import (
    CandleObservation,
    ScreenConfidence,
    ScreenObservation,
    VisualContext,
)
from screen_observer.runtime import ScreenEvent, ScreenObserverRuntime


class FakeObserver:
    def __init__(self):
        self.calls = 0
        self.contexts = [
            VisualContext(
                observed_at=pd.Timestamp("2026-10-02T09:30:00+00:00"),
                symbol="RELIANCE.NS",
                timeframe="5m",
                indicators=("EMA",),
                chart_detected=True,
                candle_observation=CandleObservation(
                    bullish=5, bearish=3, confidence=0.9
                ),
                confidence=ScreenConfidence(
                    overall=0.8,
                    symbol=0.8,
                    timeframe=0.8,
                    chart=0.8,
                    candles=0.9,
                    indicators=0.6,
                    ocr=0.7,
                ),
                provenance={"source": "desktop_screen"},
            ),
            VisualContext(
                observed_at=pd.Timestamp("2026-10-02T09:30:01+00:00"),
                symbol="TCS.NS",
                timeframe="5m",
                indicators=("EMA",),
                chart_detected=True,
                candle_observation=CandleObservation(
                    bullish=6, bearish=2, confidence=0.9
                ),
                confidence=ScreenConfidence(
                    overall=0.8,
                    symbol=0.8,
                    timeframe=0.8,
                    chart=0.8,
                    candles=0.9,
                    indicators=0.6,
                    ocr=0.7,
                ),
                provenance={"source": "desktop_screen"},
            ),
        ]

    def observe(self, *, observed_at, windows):
        self.calls += 1
        context = self.contexts[min(self.calls - 1, len(self.contexts) - 1)]
        return ScreenObservation(
            observed_at=observed_at,
            image=None,
            windows=tuple(windows),
            target_window=None,
            chart=type("Chart", (), {
                "detected": context.chart_detected,
                "left": None, "top": None, "width": None, "height": None,
                "confidence": context.confidence.chart,
            })(),
            ocr_text=(),
            symbol=context.symbol,
            timeframe=context.timeframe,
            indicators=context.indicators,
            candles=context.candle_observation,
            confidence=context.confidence,
        )

    def to_visual_context(self, observation):
        return self.contexts[min(self.calls - 1, len(self.contexts) - 1)]


def test_runtime_observe_once_emits_initial_and_changed_events():
    events = []
    runtime = ScreenObserverRuntime(
        observer=FakeObserver(),
        interval=timedelta(seconds=1),
        on_event=events.append,
    )

    runtime.observe_once()
    runtime.observe_once()

    assert [event.event_type for event in events] == [
        "SCREEN_CONNECTED",
        "VISUAL_CONTEXT_CHANGED",
    ]
    assert runtime.latest_visual_context.symbol == "TCS.NS"


def test_runtime_pause_resume_and_stop():
    calls = []
    observer = FakeObserver()

    class RuntimeObserver(FakeObserver):
        def observe(self, **kwargs):
            calls.append(True)
            return super().observe(**kwargs)

    runtime = ScreenObserverRuntime(
        observer=RuntimeObserver(),
        interval=timedelta(milliseconds=10),
    )

    runtime.start()
    time.sleep(0.04)
    runtime.pause()
    paused_count = len(calls)
    time.sleep(0.04)
    assert len(calls) == paused_count

    runtime.resume()
    time.sleep(0.04)
    runtime.stop()

    assert paused_count > 0
    assert len(calls) > paused_count
    assert not runtime.running


def test_runtime_survives_one_observation_failure():
    class FailingOnce(FakeObserver):
        def observe(self, **kwargs):
            if self.calls == 0:
                self.calls += 1
                raise RuntimeError("capture failed")
            return super().observe(**kwargs)

    runtime = ScreenObserverRuntime(
        observer=FailingOnce(),
        interval=timedelta(milliseconds=10),
    )

    runtime.start()
    time.sleep(0.05)
    runtime.stop()

    assert runtime.last_error is None
    assert runtime.latest_visual_context is not None


def test_runtime_signature_ignores_observation_timestamp():
    context = FakeObserver().contexts[0]
    signature = ScreenObserverRuntime._context_signature(context)
    shifted = VisualContext(
        observed_at=pd.Timestamp("2026-10-02T09:31:00+00:00"),
        symbol=context.symbol,
        timeframe=context.timeframe,
        indicators=context.indicators,
        chart_detected=context.chart_detected,
        candle_observation=context.candle_observation,
        confidence=context.confidence,
        provenance=context.provenance,
    )
    assert signature == ScreenObserverRuntime._context_signature(shifted)
