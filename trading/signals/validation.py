"""
Validation helpers for the research signal/candidate layer.
"""

from __future__ import annotations

import math

import pandas as pd

from .models import TradeCandidate


def validate_candidate(candidate: TradeCandidate) -> None:
    """Validate one fully constructed TradeCandidate."""

    if not isinstance(candidate, TradeCandidate):
        raise TypeError(
            "candidate must be a TradeCandidate"
        )

    timestamp = pd.Timestamp(candidate.timestamp)

    if timestamp.tzinfo is None:
        raise ValueError(
            "candidate timestamp must be timezone-aware"
        )

    if not candidate.symbol.strip():
        raise ValueError(
            "candidate symbol must not be empty"
        )

    for name, value in (
        ("entry_price", candidate.entry_price),
        ("stop_price", candidate.stop_price),
    ):
        if not math.isfinite(float(value)):
            raise ValueError(
                f"candidate {name} must be finite"
            )

        if float(value) <= 0:
            raise ValueError(
                f"candidate {name} must be positive"
            )

    if not candidate.policy_version:
        raise ValueError(
            "candidate policy_version must not be empty"
        )

    if candidate.stop_distance <= 0:
        raise ValueError(
            "candidate stop distance must be positive"
        )


def validate_candidates(
    candidates: list[TradeCandidate],
) -> None:
    """Validate a collection of research candidates."""

    if not isinstance(candidates, list):
        raise TypeError(
            "candidates must be a list"
        )

    seen: set[tuple[str, pd.Timestamp]] = set()

    for candidate in candidates:
        validate_candidate(candidate)

        key = (
            candidate.symbol.upper(),
            pd.Timestamp(candidate.timestamp),
        )

        if key in seen:
            raise ValueError(
                "duplicate candidate for symbol/timestamp: "
                f"{key}"
            )

        seen.add(key)
