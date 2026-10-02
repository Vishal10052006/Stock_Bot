import pandas as pd

from screen_observer.contracts import WindowObservation
from screen_observer.observer import ScreenObserver


class FakeCapture:
    def capture(self, region=None):
        class Image:
            size = (1200, 600)
        return Image()


def test_observer_produces_observation_without_optional_vision_dependencies():
    observer = ScreenObserver(capture_backend=FakeCapture())
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
    assert observation.confidence.overall >= 0
    context = observer.to_visual_context(observation)
    assert context.provenance["authority"] == "OBSERVATION_ONLY"
