"""S11/S15 screen-confidence aggregation and calibration."""

from __future__ import annotations

from .contracts import ScreenConfidence

_COMPONENTS = ("chart", "ocr", "symbol", "timeframe", "indicators", "candles")
_WEIGHTS = {
    "chart": 0.25,
    "ocr": 0.20,
    "symbol": 0.20,
    "timeframe": 0.15,
    "indicators": 0.10,
    "candles": 0.10,
}


def _validate_component(name: str, value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} confidence must be in [0, 1]")
    return value


def calculate_screen_confidence(
    *, chart: float, ocr: float, symbol: float, timeframe: float,
    indicators: float, candles: float,
) -> ScreenConfidence:
    values = {
        "chart": _validate_component("chart", chart),
        "ocr": _validate_component("ocr", ocr),
        "symbol": _validate_component("symbol", symbol),
        "timeframe": _validate_component("timeframe", timeframe),
        "indicators": _validate_component("indicators", indicators),
        "candles": _validate_component("candles", candles),
    }
    overall = sum(_WEIGHTS[name] * values[name] for name in _COMPONENTS)
    return ScreenConfidence(
        overall=round(overall, 4),
        symbol=round(values["symbol"], 4),
        timeframe=round(values["timeframe"], 4),
        chart=round(values["chart"], 4),
        candles=round(values["candles"], 4),
        indicators=round(values["indicators"], 4),
        ocr=round(values["ocr"], 4),
    )


def validate_screen_confidence(
    confidence: ScreenConfidence,
    *,
    minimum_overall: float = 0.55,
    minimum_chart: float = 0.45,
) -> tuple[bool, tuple[str, ...]]:
    """Return deterministic calibration result; never upgrades confidence."""

    if not 0.0 <= minimum_overall <= 1.0:
        raise ValueError("minimum_overall must be in [0, 1]")
    if not 0.0 <= minimum_chart <= 1.0:
        raise ValueError("minimum_chart must be in [0, 1]")

    reasons: list[str] = []
    for name in _COMPONENTS:
        value = float(getattr(confidence, name))
        if not 0.0 <= value <= 1.0:
            reasons.append(f"SCREEN_CONFIDENCE_{name.upper()}_OUT_OF_RANGE")

    if confidence.overall < minimum_overall:
        reasons.append("SCREEN_CONFIDENCE_OVERALL_LOW")
    if confidence.chart < minimum_chart:
        reasons.append("SCREEN_CONFIDENCE_CHART_LOW")

    return not reasons, tuple(reasons)


def screen_confidence_state(
    confidence: ScreenConfidence,
    *,
    minimum_overall: float = 0.55,
    minimum_chart: float = 0.45,
) -> str:
    """Return TRUSTED, DEGRADED, or REJECTED without changing evidence."""

    valid, reasons = validate_screen_confidence(
        confidence,
        minimum_overall=minimum_overall,
        minimum_chart=minimum_chart,
    )
    if valid:
        return "TRUSTED"

    # A structurally valid but low-confidence observation is degraded.
    # A confidence component outside [0, 1] is rejected.
    if any(reason.endswith("_OUT_OF_RANGE") for reason in reasons):
        return "REJECTED"
    return "DEGRADED"


def screen_is_usable(
    confidence: ScreenConfidence,
    *,
    minimum_overall: float = 0.55,
    require_chart: bool = True,
) -> bool:
    minimum_chart = minimum_overall if require_chart else 0.0
    valid, _ = validate_screen_confidence(
        confidence,
        minimum_overall=minimum_overall,
        minimum_chart=minimum_chart,
    )
    return valid
