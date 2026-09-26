"""M20.5 controlled outcome-learning runtime.

Consumes existing Phase-17/18 evidence and Phase-19 candidate contracts. It never
changes production Strategy/Risk/Execution configuration and never promotes a
candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any

from analysis import ErrorAnalysisReport
from candidate_improvement import (
    CandidateImprovementEngine,
    CandidateImprovementProposal,
)
from experiments import ExperimentDefinition
from journal.models import TradeDecisionRecord, TradeJournalRecord
from learning import LearningEngine, LearningExperience, LearningReport


@dataclass(frozen=True, slots=True)
class LearningEvidenceRun:
    learning: LearningReport
    candidates: tuple[CandidateImprovementProposal, ...]

    def evidence(self) -> dict[str, Any]:
        return {
            "trades_analyzed": self.learning.analyzed_trade_count,
            "trades_rewarded": self.learning.rewarded_trade_count,
            "experiences": len(self.learning.experiences),
            "candidates": len(self.candidates),
            "production_mutation": False,
            "live_broker_order_submission": False,
        }


class ControlledLearningRuntime:
    """Generate reproducible research candidates from actual outcomes."""

    def __init__(
        self,
        *,
        learning: LearningEngine | None = None,
        candidates: CandidateImprovementEngine | None = None,
    ) -> None:
        self.learning = learning or LearningEngine()
        self.candidates = candidates or CandidateImprovementEngine()

    def analyze(
        self,
        *,
        records: tuple[TradeJournalRecord, ...],
        decisions: tuple[TradeDecisionRecord, ...],
        error_analysis: ErrorAnalysisReport,
        baseline_strategy_fingerprint: str | None = None,
        experiment_definitions: Mapping[str, ExperimentDefinition] | None = None,
        parameter_changes: Mapping[str, Mapping[str, object]] | None = None,
        candidate_prefix: str = "M20",
    ) -> LearningEvidenceRun:
        report = self.learning.learn(records, error_analysis, decisions)
        definitions = experiment_definitions or {}
        changes = parameter_changes or {}
        proposals: list[CandidateImprovementProposal] = []

        if baseline_strategy_fingerprint and definitions and changes:
            for index, experience in enumerate(report.experiences, start=1):
                definition = definitions.get(experience.pattern.value)
                change_set = changes.get(experience.pattern.value)
                if definition is None or change_set is None:
                    continue
                proposal = self.candidates.propose(
                    experience,
                    baseline_strategy_fingerprint=baseline_strategy_fingerprint,
                    parameter_changes=change_set,
                    experiment_definition=definition,
                    candidate_id=f"{candidate_prefix}-CAND-{index:04d}",
                )
                proposals.append(proposal)

        return LearningEvidenceRun(
            learning=report,
            candidates=tuple(proposals),
        )
