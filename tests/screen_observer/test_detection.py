from screen_observer.contracts import WindowObservation
from screen_observer.detection import TradingViewRegionDetector, WindowDetector


def window(title="RELIANCE - TradingView"):
    return WindowObservation(
        title=title,
        application="Chrome",
        left=10,
        top=20,
        width=1200,
        height=800,
    )


def test_window_detector_finds_tradingview():
    detected = WindowDetector().select([window()])
    assert detected is not None
    assert detected.title == "RELIANCE - TradingView"


def test_window_detector_returns_none_for_other_window():
    assert WindowDetector().select([
        WindowObservation("Terminal", "gnome-terminal", 0, 0, 800, 600)
    ]) is None


def test_tradingview_region_is_inside_target_window():
    chart = TradingViewRegionDetector().detect(window())
    assert chart.detected
    assert chart.left == 10
    assert chart.top > 20
    assert chart.width == 1200
    assert chart.height < 800


def test_chart_detector_rejects_blank_frame():
    import numpy as np

    detector = TradingViewRegionDetector()
    blank = np.full((600, 1200, 3), 255, dtype=np.uint8)
    chart = detector.detect(window(), image=blank)
    assert not chart.detected


def test_chart_detector_uses_visual_evidence_and_stays_inside_window(monkeypatch):
    import numpy as np

    detector = TradingViewRegionDetector()

    fake_image = np.zeros((800, 1200, 3), dtype=np.uint8)

    def fake_recognize_chart(image):
        return True, 0.75

    monkeypatch.setattr(
        "screen_observer.vision.recognize_chart",
        fake_recognize_chart,
    )

    chart = detector.detect(window(), image=fake_image)
    assert chart.detected
    assert 10 <= chart.left < 10 + 1200
    assert 20 <= chart.top < 20 + 800
    assert chart.left + chart.width <= 10 + 1200
    assert chart.top + chart.height <= 20 + 800
    assert chart.confidence > 0.0


def test_chart_detector_ocr_is_supporting_evidence_only(monkeypatch):
    import numpy as np
    from types import SimpleNamespace

    detector = TradingViewRegionDetector()
    fake_image = np.zeros((800, 1200, 3), dtype=np.uint8)

    monkeypatch.setattr(
        "screen_observer.vision.recognize_chart",
        lambda image: (True, 0.75),
    )

    token = SimpleNamespace(left=100, top=300, width=100, height=20)
    result = SimpleNamespace(tokens=(token,))
    chart = detector.detect(window(), image=fake_image, ocr_result=result)
    assert chart.detected
    assert chart.confidence > 0.66
