"""S11 confidence aggregation and usability gate."""

from __future__ import annotations

from .contracts import ScreenConfidence


def calculate_screen_confidence(
    *,
    chart: float,
    ocr: float,
    symbol: float,
    timeframe: float,
    indicators: float,
    candles: float,
) -> ScreenConfidence:
    values = {
        "chart": chart,
        "ocr": ocr,
        "symbol": symbol,
        "timeframe": timeframe,
        "indicators": indicators,
        "candles": candles,
    }
    for name, value in values.items():
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{name} confidence must be in [0, 1]")

    # Identity and chart geometry are stronger prerequisites than optional
    # indicator/candle observations.
    overall = (
        0.25 * chart
        + 0.20 * ocr
        + 0.20 * symbol
        + 0.15 * timeframe
        + 0.10 * indicators
        + 0.10 * candles
    )
    return ScreenConfidence(
        overall=round(overall, 4),
        symbol=round(symbol, 4),
        timeframe=round(timeframe, 4),
        chart=round(chart, 4),
        candles=round(candles, 4),
        indicators=round(indicators, 4),
        ocr=round(ocr, 4),
    )


def screen_is_usable(
    confidence: ScreenConfidence,
    *,
    minimum_overall: float = 0.55,
    require_chart: bool = True,
) -> bool:
    if not 0.0 <= minimum_overall <= 1.0:
        raise ValueError("minimum_overall must be in [0, 1]")
    if require_chart and (confidence.chart < minimum_overall or confidence.overall < minimum_overall):
        return False
    return confidence.overall >= minimum_overall
