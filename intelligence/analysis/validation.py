"""Validation rules for AnalysisInput/AnalysisContext."""
from __future__ import annotations

from typing import Mapping, Any

import pandas as pd

from intelligence.analysis.contracts import AnalysisContext


def validate_analysis_context(context: AnalysisContext) -> AnalysisContext:
    """Validate the immutable AnalysisContext boundary."""
    if not isinstance(context, AnalysisContext):
        raise TypeError("context must be an AnalysisContext")
    if pd.Timestamp(context.timestamp).tzinfo is None:
        raise ValueError("analysis timestamp must be timezone-aware")
    if not context.symbol:
        raise ValueError("analysis symbol must not be empty")
    if any(value != value for value in context.provenance.values() if isinstance(value, float)):
        raise ValueError("provenance contains NaN")
    return context


def validate_feature_mapping(features: Mapping[str, Any]) -> None:
    """Reject NaN/inf numeric scalar feature values."""
    for name, value in features.items():
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number != number or number in (float("inf"), float("-inf")):
            raise ValueError(f"invalid feature value for {name}")
