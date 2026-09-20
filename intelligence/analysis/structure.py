"""Price-structure interpretation using existing Phase 4/5 fields."""
from __future__ import annotations
from typing import Any, Mapping


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"true", "1"}:
        return True
    if str(value).lower() in {"false", "0"}:
        return False
    return None


def analyze_structure(features: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize higher/lower structure, breakout and retest evidence."""
    hh = _bool(features.get("higher_high"))
    hl = _bool(features.get("higher_low"))
    lh = _bool(features.get("lower_high"))
    ll = _bool(features.get("lower_low"))
    retest_up = _bool(features.get("retest_up"))
    retest_down = _bool(features.get("retest_down"))

    if hh is True and hl is True and lh is not True and ll is not True:
        trend = "BULLISH"
    elif lh is True and ll is True and hh is not True and hl is not True:
        trend = "BEARISH"
    elif any(v is True for v in (hh, hl, lh, ll)):
        trend = "MIXED"
    else:
        trend = "UNKNOWN"

    if retest_up is True and retest_down is not True:
        retest = "UP_CONFIRMED"
    elif retest_down is True and retest_up is not True:
        retest = "DOWN_CONFIRMED"
    elif retest_up is True and retest_down is True:
        retest = "CONFLICT"
    else:
        retest = "NONE"

    return {
        "trend": trend,
        "higher_high": hh,
        "higher_low": hl,
        "lower_high": lh,
        "lower_low": ll,
        "retest": retest,
        "opening_range_context_available": (
            features.get("opening_range_high_distance_pct") is not None
            or features.get("opening_range_low_distance_pct") is not None
        ),
    }
