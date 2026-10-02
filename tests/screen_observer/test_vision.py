from PIL import Image, ImageDraw

from screen_observer.vision import (
    detect_indicators,
    detect_symbol,
    detect_timeframe,
    parse_candles,
    recognize_chart,
)


def _synthetic_chart() -> Image.Image:
    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)

    # Plot/grid structure for S05.
    for y in range(80, 460, 60):
        draw.line((40, y, 860, y), fill=(215, 215, 215), width=1)
    for x in range(80, 860, 100):
        draw.line((x, 60, x, 460), fill=(225, 225, 225), width=1)

    # Synthetic candles for S06: wick + body, with explicit bullish/bearish
    # colors matching common chart conventions.
    candles = [
        (120, 320, 145, 380, (30, 170, 70)),
        (190, 250, 215, 330, (210, 45, 55)),
        (260, 280, 285, 350, (30, 170, 70)),
        (330, 220, 355, 300, (210, 45, 55)),
        (400, 250, 425, 325, (30, 170, 70)),
        (470, 180, 495, 270, (30, 170, 70)),
        (540, 210, 565, 290, (210, 45, 55)),
        (610, 160, 635, 250, (30, 170, 70)),
    ]
    for left, top, right, bottom, color in candles:
        center = (left + right) // 2
        draw.line((center, top - 18, center, bottom + 18), fill=color, width=3)
        draw.rectangle((left, top, right, bottom), fill=color)

    return image



def _synthetic_terminal_ui() -> Image.Image:
    """Text-heavy UI fixture used to guard against chart false positives."""
    image = Image.new("RGB", (900, 500), (24, 24, 24))
    draw = ImageDraw.Draw(image)

    # Simulate terminal/editor text with many short colored glyph-like runs.
    for row in range(35, 470, 24):
        for col in range(20, 820, 85):
            color = (60, 210, 110) if (row // 24 + col // 85) % 3 else (220, 70, 70)
            draw.rectangle((col, row, col + 24, row + 3), fill=color)
            draw.rectangle((col + 4, row - 6, col + 7, row + 6), fill=color)

    # A terminal prompt-like long line is intentionally shorter than chart
    # grid spacing requirements and should not qualify as plot structure.
    for y in (120, 260, 400):
        draw.line((20, y, 700, y), fill=(55, 55, 55), width=1)
    draw.line((20, 486, 300, 486), fill=(90, 90, 90), width=1)
    return image

def test_detect_symbol_is_conservative():
    symbol, confidence = detect_symbol(["RELIANCE.NS", "5m", "₹1420"])
    assert symbol == "RELIANCE.NS"
    assert confidence > 0

def test_detect_symbol_handles_tradingview_exchange_prefix():
    symbol, confidence = detect_symbol(["NSE:RELIANCE", "5m"])
    assert symbol == "RELIANCE.NS"
    assert confidence == 0.80


def test_detect_timeframe():
    timeframe, confidence = detect_timeframe(["RELIANCE", "5m"])
    assert timeframe == "5m"
    assert confidence > 0


def test_detect_indicators():
    indicators, confidence = detect_indicators(["EMA 20", "VWAP", "RSI"])
    assert indicators == ("EMA", "RSI", "VWAP")
    assert confidence > 0


def test_chart_sanity_check():
    assert recognize_chart(Image.new("RGB", (1200, 700), "white"))[0] is False
    assert recognize_chart(Image.new("RGB", (100, 80), "white")) == (False, 0.0)


def test_chart_recognition_detects_synthetic_plot_structure():
    detected, confidence = recognize_chart(_synthetic_chart())
    assert detected is True
    assert confidence >= 0.35


def test_candle_parser_counts_colored_candidates():
    observation = parse_candles(_synthetic_chart())
    assert observation.bullish >= 3
    assert observation.bearish >= 2
    assert observation.confidence > 0.5


def test_candle_parser_does_not_invent_candles_from_blank_image():
    blank = Image.new("RGB", (900, 500), "white")
    observation = parse_candles(blank)
    assert observation.bullish == 0
    assert observation.bearish == 0
    assert observation.confidence == 0.0

def test_chart_recognition_rejects_text_heavy_ui():
    detected, confidence = recognize_chart(_synthetic_terminal_ui())
    assert detected is False
    assert confidence < 0.45


def test_candle_parser_rejects_colored_ui_text():
    observation = parse_candles(_synthetic_terminal_ui())
    assert observation.bullish == 0
    assert observation.bearish == 0
    assert observation.confidence == 0.0

