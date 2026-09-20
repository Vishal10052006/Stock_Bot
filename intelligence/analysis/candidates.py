"""Analytical candidate generation; never creates trade orders."""
from __future__ import annotations
from typing import Any, Mapping


def generate_candidates(technical: Mapping[str, Any], structure: Mapping[str, Any], volume: Mapping[str, Any], relative: Mapping[str, Any]) -> tuple[str, ...]:
    """Return auditable analytical candidates, not strategy decisions."""
    candidates: list[str] = []
    if technical.get("direction") == "BULLISH":
        candidates.append("trend_aligned_long_context")
    elif technical.get("direction") == "BEARISH":
        candidates.append("trend_aligned_short_context")
    if volume.get("confirmation"):
        candidates.append("volume_confirmation")
    if structure.get("retest") == "UP_CONFIRMED":
        candidates.append("retest_up_candidate")
    elif structure.get("retest") == "DOWN_CONFIRMED":
        candidates.append("retest_down_candidate")
    if relative.get("relative_strength"):
        candidates.append("relative_strength_context")
    elif relative.get("relative_weakness"):
        candidates.append("relative_weakness_context")
    return tuple(candidates)
