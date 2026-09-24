"""End-to-end controlled self-learning orchestration.

The orchestrator composes the repository's existing journal, error analysis,
learning evidence, experiment, candidate, monitoring, and model-registry
boundaries. It records what was observed and what is eligible for research;
it does not place orders or silently mutate production state.

References:
    Self-learning master specification, especially the canonical loop and
    promotion controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from analysis import ErrorAnalysisReport, TradeErrorAnalyzer
from journal.models import TradeDecisionRecord, TradeJournalRecord
from ml.model_registry import ModelRegistry, ModelRegistryRecord

from candidate_improvement.engine import CandidateImprovementEngine
from experiments.definition import ExperimentDefinition
from experiments.evaluation import EvaluationReport, evaluate_experiment_record
from experiments.lineage import LineageRecord, build_lineage
from experiments.record import ExperimentRecord

from .cycle_store import LearningCycleStore
from .engine import LearningEngine
from .experiment_store import ExperimentRegistry
from .self_learning_models import (
    ExperimentLineage,
    LearningCycle,
    LearningDecision,
    LearningState,
)


@dataclass(frozen=True, slots=True)
class SelfLearningRun:
    """Immutable output of one evidence-processing cycle."""

    cycle: LearningCycle
    audit: object
    analysis: ErrorAnalysisReport
    learning_report: object
    experiment_evaluation: EvaluationReport | None = None
    candidate_validation: object | None = None


class SelfLearningEngine:
    """Compose evidence processing without granting trading authority."""

    def __init__(
        self,
        *,
        learning_engine: LearningEngine | None = None,
        experiment_registry: ExperimentRegistry | None = None,
        cycle_store: LearningCycleStore | None = None,
        model_registry: ModelRegistry | None = None,
    ) -> None:
        self.learning_engine = learning_engine or LearningEngine()
        self.experiment_registry = experiment_registry
        self.cycle_store = cycle_store
        self.model_registry = model_registry

    def observe(
        self,
        decisions: Iterable[TradeDecisionRecord],
        outcomes: Iterable[TradeJournalRecord],
        *,
        cycle_id: str,
    ) -> SelfLearningRun:
        """Process linked trade evidence into learning experiences."""
        decision_tuple = tuple(decisions)
        outcome_tuple = tuple(outcomes)

        from .experience import audit_journal_linkage

        audit = audit_journal_linkage(decision_tuple, outcome_tuple)
        if not audit.valid:
            cycle = LearningCycle(
                cycle_id=cycle_id,
                state=LearningState.INCONCLUSIVE,
                experience_fingerprints=(),
                learning_evidence_fingerprints=(),
                experiment_id=None,
                candidate_id=None,
                promotion_review_fingerprint=None,
                decision=LearningDecision.INCONCLUSIVE,
                lesson="Experience audit failed; no learning action was authorized.",
                next_experiment="Repair journal linkage before learning.",
            )
            self._persist_cycle(cycle)
            raise ValueError(
                "self-learning observation blocked by experience audit: "
                + "; ".join(audit.causal_violations)
                if audit.causal_violations
                else "self-learning observation blocked by journal linkage"
            )

        analysis = TradeErrorAnalyzer().analyze_linked(
            decision_tuple,
            outcome_tuple,
        )
        learning_report = self.learning_engine.learn(
            outcome_tuple,
            analysis,
            decision_tuple,
        )

        from .experience import build_trade_experience

        experiences = []
        decision_map = {item.trade_id: item for item in decision_tuple}
        for outcome in outcome_tuple:
            decision = decision_map.get(outcome.trade_id)
            if decision is None or decision.direction == "NO_TRADE":
                continue
            experiences.append(build_trade_experience(decision, outcome))

        cycle = LearningCycle(
            cycle_id=cycle_id,
            state=(
                LearningState.HYPOTHESIS
                if learning_report.experiences
                else LearningState.INCONCLUSIVE
            ),
            experience_fingerprints=tuple(item.fingerprint for item in experiences),
            learning_evidence_fingerprints=tuple(
                item.fingerprint
                for item in learning_report.experiences
            ),
            experiment_id=None,
            candidate_id=None,
            promotion_review_fingerprint=None,
            decision=(
                LearningDecision.REDESIGN
                if learning_report.experiences
                else LearningDecision.INCONCLUSIVE
            ),
            lesson=(
                "Evidence is available for controlled research."
                if learning_report.experiences
                else "No learning experiment is justified by the supplied evidence."
            ),
            next_experiment=(
                "Create one frozen hypothesis and change one primary variable."
                if learning_report.experiences
                else "Collect additional valid trade evidence."
            ),
        )
        self._persist_cycle(cycle)

        return SelfLearningRun(
            cycle=cycle,
            audit=audit,
            analysis=analysis,
            learning_report=learning_report,
        )

    def record_experiment(
        self,
        *,
        definition: ExperimentDefinition,
        record: ExperimentRecord,
        lineage: LineageRecord,
    ) -> EvaluationReport:
        """Validate and persist an immutable experiment result."""
        evaluation = evaluate_experiment_record(record)

        if self.experiment_registry is not None:
            self.experiment_registry.append(
                definition,
                record,
                lineage,
            )

        return evaluation

    def validate_candidate(
        self,
        *,
        candidate: object,
        experiment_definition: ExperimentDefinition,
        experiment_record: ExperimentRecord,
    ) -> object:
        """Validate candidate research wiring against an experiment result."""
        evaluation = evaluate_experiment_record(experiment_record)
        return CandidateImprovementEngine.validate(
            candidate,  # type: ignore[arg-type]
            minimum_evidence=3,
            minimum_confidence=0.0,
        ) if evaluation.valid else CandidateImprovementEngine.validate(
            candidate,  # type: ignore[arg-type]
            minimum_evidence=3,
            minimum_confidence=1.0,
        )

    def _persist_cycle(self, cycle: LearningCycle) -> None:
        """Persist a cycle only when a cycle store was explicitly configured."""
        if self.cycle_store is not None:
            self.cycle_store.append(cycle)


__all__ = ["SelfLearningEngine", "SelfLearningRun"]
