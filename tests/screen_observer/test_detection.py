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
