"""Analysis-quality evaluation helpers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from intelligence.analysis.contracts import AnalysisContext


@dataclass(frozen=True, slots=True)
class AnalysisEvaluation:
    """Non-profitability quality evaluation for Analysis Bot."""
    contexts: int
    complete_contexts: int
    average_feature_completeness: float
    deterministic_schema: bool


def evaluate_contexts(contexts: Iterable[AnalysisContext]) -> AnalysisEvaluation:
    """Evaluate coverage/completeness without using future outcomes."""
    rows = tuple(contexts)
    complete = [c for c in rows if float(c.quality.get("completeness", 0.0)) >= 0.95]
    avg = sum(float(c.quality.get("completeness", 0.0)) for c in rows) / len(rows) if rows else 0.0
    return AnalysisEvaluation(
        contexts=len(rows),
        complete_contexts=len(complete),
        average_feature_completeness=avg,
        deterministic_schema=all(isinstance(c.analysis_version, str) for c in rows),
    )
