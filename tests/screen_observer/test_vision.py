from dataclasses import dataclass

from screen_observer.vision import (
    detect_indicators,
    detect_symbol,
    detect_timeframe,
    recognize_chart,
)


@dataclass
class FakeImage:
    size: tuple[int, int]


def test_detect_symbol_is_conservative():
    symbol, confidence = detect_symbol(["RELIANCE.NS", "5m", "₹1420"])
    assert symbol == "RELIANCE.NS"
    assert confidence > 0


def test_detect_timeframe():
    timeframe, confidence = detect_timeframe(["RELIANCE", "5m"])
    assert timeframe == "5m"
    assert confidence > 0


def test_detect_indicators():
    indicators, confidence = detect_indicators(["EMA 20", "VWAP", "RSI"])
    assert indicators == ("EMA", "RSI", "VWAP")
    assert confidence > 0


def test_chart_sanity_check():
    assert recognize_chart(FakeImage((1200, 700))) == (True, 0.45)
    assert recognize_chart(FakeImage((100, 80))) == (False, 0.0)
