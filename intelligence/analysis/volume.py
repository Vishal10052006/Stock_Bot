"""Volume interpretation using existing causal volume features."""
from __future__ import annotations
from typing import Any, Mapping


def analyze_volume(features: Mapping[str, Any]) -> dict[str, Any]:
    """Interpret RVOL and volume-change evidence without issuing a signal."""
    def numeric(name: str) -> float | None:
        try:
            value = features.get(name)
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    rvol = numeric("rvol_20")
    change = numeric("volume_change_1")
    if rvol is None:
        state = "UNAVAILABLE"
    elif rvol >= 1.5:
        state = "HIGH"
    elif rvol >= 1.0:
        state = "NORMAL"
    else:
        state = "LOW"

    return {
        "rvol": rvol,
        "volume_change": change,
        "state": state,
        "confirmation": rvol is not None and rvol >= 1.0,
        "abnormal": rvol is not None and rvol >= 2.0,
    }
