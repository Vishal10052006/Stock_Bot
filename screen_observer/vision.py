"""Visual interpreters for Screen Observer S04-S08.

The implementations are deliberately conservative:
- OCR remains optional.
- S05 uses image geometry/edge structure to distinguish chart-like regions
  from arbitrary small images.
- S06 detects visually supported bullish/bearish candle candidates without
  attempting to manufacture numerical OHLC values.
- Missing/ambiguous evidence returns low confidence rather than a guess.

References:
- Screen Intelligence roadmap S04-S08.
- TRADING_SPECIFICATION.md: screen observation is contextual evidence and the
  authoritative market feed remains upstream of trading decisions.
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


def _as_rgb_array(image: Any):
    """Convert common screenshot/image objects to an RGB uint8 ndarray."""
    import numpy as np

    array = np.asarray(image)
    if array.ndim == 2:
        return np.repeat(array[:, :, None], 3, axis=2).astype(np.uint8)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError("image must be a grayscale, RGB, or RGBA image")

    array = array.astype(np.uint8, copy=False)

    # MSS returns BGRA/BGR while PIL and most test fixtures use RGB/RGBA.
    # Detect the common MSS pixel object explicitly when available.
    if array.shape[2] == 4:
        try:
            import mss.base
            if isinstance(image, mss.base.ScreenShot):
                return array[:, :, :3][:, :, ::-1].copy()
        except (ImportError, AttributeError):
            pass
        return array[:, :, :3]

    return array


def recognize_chart(image: Any) -> tuple[bool, float]:
    """S05 chart recognition using conservative edge/line structure.

    A chart-like image should contain enough edges to represent plot/grid
    structure without being almost entirely an edge map. This is intentionally
    a recognition signal, not a semantic claim that the image is TradingView.
    """
    try:
        import cv2
        import numpy as np

        rgb = _as_rgb_array(image)
        height, width = rgb.shape[:2]
        if width < 200 or height < 120:
            return False, 0.0

        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.count_nonzero(edges)) / float(edges.size)

        horizontal = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=max(25, width // 12),
            minLineLength=max(30, width // 8),
            maxLineGap=8,
        )
        vertical = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=max(20, height // 10),
            minLineLength=max(25, height // 8),
            maxLineGap=8,
        )

        horizontal_count = 0 if horizontal is None else len(horizontal)
        vertical_count = 0 if vertical is None else len(vertical)

        # Chart-like structure needs a moderate edge field plus horizontal
        # and/or vertical plot/grid structure. Extremely edge-dense images
        # are rejected as likely UI/text/noise.
        density_score = min(1.0, edge_density / 0.10)
        structure_score = min(1.0, (horizontal_count + vertical_count) / 8.0)
        score = round(0.55 * density_score + 0.45 * structure_score, 4)

        detected = (
            0.015 <= edge_density <= 0.22
            and (horizontal_count >= 2 or vertical_count >= 2)
            and score >= 0.35
        )
        return detected, score if detected else min(score, 0.30)
    except (ImportError, ValueError, TypeError):
        return False, 0.0


def _color_masks(rgb):
    """Return common TradingView-style red and green pixel masks."""
    import cv2

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    vivid = (saturation >= 90) & (value >= 70)
    red = vivid & ((hsv[:, :, 0] <= 12) | (hsv[:, :, 0] >= 170))
    green = vivid & (hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 95)
    return red.astype("uint8") * 255, green.astype("uint8") * 255


def _count_candle_candidates(mask) -> int:
    """Count compact, filled colored structures consistent with candles."""
    import cv2

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    count = 0
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        box_area = float(width * height)
        if box_area <= 0:
            continue

        fill_ratio = area / box_area
        aspect_ratio = height / max(width, 1)

        # Candle body + wick often forms a narrow vertical component. Reject
        # very thin lines and huge plot-wide indicator structures.
        if (
            3 <= width <= 32
            and 6 <= height <= 140
            and 0.04 <= fill_ratio <= 0.99
            and aspect_ratio <= 18
            and area >= 8
        ):
            count += 1

    return count


def parse_candles(image: Any) -> CandleObservation:
    """S06 detect visually supported bullish/bearish candle candidates.

    The parser reports counts only. It does not infer OHLC prices, timestamps,
    or market direction. Confidence reflects the amount and consistency of
    visible colored candle evidence.
    """
    try:
        import numpy as np

        rgb = _as_rgb_array(image)
        red_mask, green_mask = _color_masks(rgb)
        bearish = _count_candle_candidates(red_mask)
        bullish = _count_candle_candidates(green_mask)
        total = bullish + bearish

        if total == 0:
            return CandleObservation(confidence=0.0)

        # More independent candidates and a balanced visual sample increase
        # confidence, while a single candidate remains deliberately weak.
        sample_score = min(1.0, total / 12.0)
        class_score = 1.0 if bullish and bearish else 0.70
        confidence = round(0.35 + 0.45 * sample_score + 0.20 * class_score, 4)

        return CandleObservation(
            bullish=bullish,
            bearish=bearish,
            confidence=min(1.0, confidence),
        )
    except (ImportError, ValueError, TypeError):
        return CandleObservation(confidence=0.0)


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
