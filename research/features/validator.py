"""RB-13 research-feature validation.

Research features are evidence variables, not guaranteed predictive signals.
"""
from __future__ import annotations
from datetime import datetime
from typing import Mapping


def validate_feature_row(*, decision_time: datetime, available_at: datetime, features: Mapping[str, object]) -> None:
    if available_at > decision_time:
        raise ValueError("research feature contains information unavailable at decision time")
    forbidden = {k.lower() for k in features} & {
        "future_return", "future_price", "target_price", "outcome_timestamp", "label"
    }
    if forbidden:
        raise ValueError(f"future/target fields are forbidden in research features: {sorted(forbidden)}")
