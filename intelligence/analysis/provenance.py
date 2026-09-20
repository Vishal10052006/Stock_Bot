"""Provenance and quality helpers for AnalysisContext."""
from __future__ import annotations
from typing import Any, Mapping


def build_provenance(*, data_version: str, feature_version: str, analysis_version: str, sources: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build stable provenance metadata for one analysis result."""
    return {
        "data_version": data_version,
        "feature_version": feature_version,
        "analysis_version": analysis_version,
        "sources": dict(sources or {}),
        "causal_boundary": "information_available_at_decision_timestamp",
    }


def feature_quality(features: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize missing/non-finite scalar feature health."""
    missing = 0
    finite = 0
    total = len(features)
    for value in features.values():
        if value is None:
            missing += 1
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            finite += 1
            continue
        if numeric != numeric or numeric in (float("inf"), float("-inf")):
            missing += 1
        else:
            finite += 1
    return {
        "total_features": total,
        "missing_or_invalid": missing,
        "finite_or_non_numeric_valid": finite,
        "completeness": (finite / total) if total else 0.0,
    }
