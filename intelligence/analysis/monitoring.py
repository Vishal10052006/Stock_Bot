"""Monitoring primitives for Analysis Bot health."""
from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter

from intelligence.analysis.contracts import AnalysisContext


@dataclass(frozen=True, slots=True)
class AnalysisMetrics:
    """Observable metrics emitted by one analysis run."""
    success: bool
    latency_seconds: float
    feature_count: int
    missing_or_invalid: int
    completeness: float
    analysis_version: str


def measure_analysis(context: AnalysisContext, started_at: float) -> AnalysisMetrics:
    """Build metrics from a completed AnalysisContext."""
    quality = context.quality
    return AnalysisMetrics(
        success=True,
        latency_seconds=max(0.0, perf_counter() - started_at),
        feature_count=int(quality.get("total_features", len(context.feature_vector))),
        missing_or_invalid=int(quality.get("missing_or_invalid", 0)),
        completeness=float(quality.get("completeness", 0.0)),
        analysis_version=context.analysis_version,
    )
