import pandas as pd

from screen_observer.contracts import ChartObservation, WindowObservation
from screen_observer.observer import ScreenObserver


class FakeCapture:
    def capture(self, region=None):
        class Image:
            size = (1200, 600)
        return Image()


class FakeRegionDetector:
    def detect(self, window, image=None, ocr_result=None):
        return ChartObservation(
            detected=True,
            left=window.left,
            top=window.top + 100,
            width=window.width,
            height=window.height - 100,
            confidence=0.80,
        )


def test_observer_produces_observation_without_optional_vision_dependencies():
    observer = ScreenObserver(
        capture_backend=FakeCapture(),
        region_detector=FakeRegionDetector(),
    )
    observation = observer.observe(
        observed_at=pd.Timestamp("2026-10-02T09:30:00+05:30"),
        windows=[
            WindowObservation(
                title="RELIANCE - TradingView",
                application="Chrome",
                left=0,
                top=0,
                width=1200,
                height=800,
            )
        ],
    )

    assert observation.chart.detected
    assert observation.chart.confidence == 0.80
    assert observation.confidence.overall >= 0
    context = observer.to_visual_context(observation)
    assert context.provenance["authority"] == "OBSERVATION_ONLY"
