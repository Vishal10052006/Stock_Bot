"""RB-8 impact analysis contract with explicit uncertainty."""
from __future__ import annotations
from research.contracts import ImpactResult, ResearchEvent


class RuleImpactAnalyzer:
    def analyze(self, event: ResearchEvent) -> ImpactResult:
        # Baseline: importance is evidence strength, not expected return.
        sign = 1.0 if event.event_type.value in {"EARNINGS", "GUIDANCE"} else 0.0
        return ImpactResult(company=sign * event.importance if event.symbol else None,
                            sector=None, market=None, horizon="unknown",
                            confidence=min(event.confidence, 0.6))
