"""Baseline visual interpreters for S04-S08.

These are intentionally conservative. OCR and computer-vision libraries are
optional; absence of a backend produces an explicit low-confidence result
rather than fabricated market information.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .contracts import CandleObservation


INDICATORS = (
    "SMA",
    "EMA",
    "RSI",
    "MACD",
    "VWAP",
    "BOLLINGER",
    "SUPERTREND",
    "VOLUME",
)

_TIMEFRAME_PATTERNS = (
    (re.compile(r"\b(\d+)\s*m(?:in)?\b", re.I), lambda m: f"{m.group(1)}m"),
    (re.compile(r"\b(\d+)\s*h(?:our)?\b", re.I), lambda m: f"{m.group(1)}h"),
    (re.compile(r"\b(\d+)\s*d(?:ay)?\b", re.I), lambda m: f"{m.group(1)}D"),
    (re.compile(r"\b(\d+)\s*w(?:eek)?\b", re.I), lambda m: f"{m.group(1)}W"),
)


def ocr(image: Any) -> tuple[str, ...]:
    """S04 OCR adapter using pytesseract when installed."""
    try:
        import pytesseract
    except ImportError:
        return ()

    try:
        text = pytesseract.image_to_string(image)
    except Exception:
        return ()
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def detect_timeframe(text: Iterable[str]) -> tuple[str | None, float]:
    joined = " ".join(text)
    for pattern, formatter in _TIMEFRAME_PATTERNS:
        match = pattern.search(joined)
        if match:
            return formatter(match), 0.85
    # TradingView commonly displays bare intervals such as "5m".
    bare = re.search(r"\b(1|3|5|15|30|45|60|120|240)\s*m\b", joined, re.I)
    if bare:
        return f"{bare.group(1)}m", 0.80
    return None, 0.0


def detect_indicators(text: Iterable[str]) -> tuple[tuple[str, ...], float]:
    joined = " ".join(text).upper()
    found: list[str] = []
    for indicator in INDICATORS:
        aliases = {
            "BOLLINGER": ("BOLLINGER", "BB"),
            "SUPERTREND": ("SUPERTREND",),
        }.get(indicator, (indicator,))
        if any(re.search(rf"\b{re.escape(alias)}\b", joined) for alias in aliases):
            found.append(indicator)
    return tuple(found), (min(1.0, 0.50 + 0.10 * len(found)) if found else 0.0)


def detect_symbol(text: Iterable[str]) -> tuple[str | None, float]:
    """Conservative ticker extraction; avoids guessing from arbitrary OCR."""
    for line in text:
        candidate = re.sub(r"[^A-Za-z0-9._-]", "", line).upper()
        if re.fullmatch(r"[A-Z][A-Z0-9.-]{1,19}(?:\.NS)?", candidate):
            return candidate, 0.65
    return None, 0.0


def parse_candles(image: Any) -> CandleObservation:
    """S06 baseline.

    Exact OHLC recovery from pixels is intentionally not claimed here. If
    OpenCV is available, a future detector can be plugged in behind this
    contract. Returning zero counts with zero confidence is safer than
    inventing candle values.
    """
    _ = image
    return CandleObservation(bullish=0, bearish=0, confidence=0.0)


def recognize_chart(image: Any) -> tuple[bool, float]:
    """S05 minimal sanity check based on image shape when available."""
    try:
        width, height = image.size
    except AttributeError:
        try:
            width, height = image.width, image.height
        except AttributeError:
            return False, 0.0

    if width < 200 or height < 120:
        return False, 0.0
    return True, 0.45


def build_confidence(
    *,
    chart: float,
    ocr_confidence: float,
    symbol: float,
    timeframe: float,
    indicators: float,
    candles: float,
) -> float:
    values = (chart, ocr_confidence, symbol, timeframe, indicators, candles)
    return round(sum(values) / len(values), 4)
