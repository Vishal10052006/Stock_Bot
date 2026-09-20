"""Versioning helpers for Analysis Bot artifacts."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalysisVersion:
    """Explicit version tuple for reproducibility."""
    data_version: str
    feature_version: str
    indicator_version: str
    analysis_version: str
    research_version: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "data_version": self.data_version,
            "feature_version": self.feature_version,
            "indicator_version": self.indicator_version,
            "analysis_version": self.analysis_version,
            "research_version": self.research_version,
        }
