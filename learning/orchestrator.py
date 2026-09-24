"""End-to-end controlled self-learning orchestration.

This service composes the existing Phase 16-20 implementation and adds the
missing governance wiring. It records evidence and research state only; it
does not execute trades, mutate hard risk controls, or silently promote models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from analysis import ErrorAnalysisReport, TradeErrorAnalyzer
from candidate_improvement.engine import CandidateImprovementEngine
from experiments.definition import ExperimentDefinition
from experiments.evaluation import EvaluationReport, evaluate_experiment_record
from experiments.lineage import LineageRecord
from experiments.record import ExperimentRecord
from journal.models import TradeDecisionRecord, TradeJournalRecord

from .cycle_store import LearningCycleStore
from .engine import LearningEngine
from .experiment_store import ExperimentRegistry
from .self_learning_models import (
    LearningCycle,
    LearningDecision,
    LearningState,
)
from .validation import ValidationBundle


@dataclass(frozen=True, slots=True)
class SelfLearningRun:
    """Immutable result of the evidence-processing part of a learning cycle."""

    cycle: LearningCycle
    audit: object
    analysis: ErrorAnalysisReport
    learning_report: object


class SelfLearningEngine:
    """Evidence-first learning coordinator."""

    def __init__(
        self,
        *,
        learning_engine: LearningEngine | None = None,
        experiment_registry: ExperimentRegistry | None = None,
        cycle_store: LearningCycleStore | None = None,
    ) -> None:
        self.learning_engine = learning_engine or LearningEngine()
        self.experiment_registry = experiment_registry
        self.cycle_store = cycle_store

    def observe(
        self,
        decisions: Iterable[TradeDecisionRecord],
        outcomes: Iterable[TradeJournalRecord],
        *,
        cycle_id: str,
    ) -> SelfLearningRun:
        """Audit linked outcomes and convert them into learning evidence."""
        from .experience import audit_journal_linkage, build_trade_experience

        decision_tuple = tuple(decisions)
        outcome_tuple = tuple(outcomes)
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
                lesson="Experience audit failed; learning was blocked.",
                next_experiment="Repair journal linkage and causal violations.",
            )
            self._persist_cycle(cycle)
            raise ValueError(
                "self-learning observation blocked by experience audit"
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

        decision_map = {item.trade_id: item for item in decision_tuple}
        experiences = tuple(
            build_trade_experience(decision_map[outcome.trade_id], outcome)
            for outcome in outcome_tuple
            if outcome.trade_id in decision_map
            and decision_map[outcome.trade_id].direction in {"LONG", "SHORT"}
        )

        has_evidence = bool(learning_report.experiences)
        cycle = LearningCycle(
            cycle_id=cycle_id,
            state=(
                LearningState.HYPOTHESIS
                if has_evidence
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
                if has_evidence
                else LearningDecision.INCONCLUSIVE
            ),
            lesson=(
                "Evidence is available for a controlled experiment."
                if has_evidence
                else "No learning experiment is justified by the supplied evidence."
            ),
            next_experiment=(
                "Create one frozen experiment and change one primary variable."
                if has_evidence
                else "Collect additional valid completed-trade evidence."
            ),
        )
        self._persist_cycle(cycle)

        return SelfLearningRun(
            cycle=cycle,
            audit=audit,
            analysis=analysis,
            learning_report=learning_report,
        )

    def register_experiment(
        self,
        *,
        definition: ExperimentDefinition,
        record: ExperimentRecord,
        lineage: LineageRecord,
    ) -> EvaluationReport:
        """Validate and optionally persist an immutable experiment result."""
        evaluation = evaluate_experiment_record(record)

        if self.experiment_registry is not None:
            self.experiment_registry.append(
                definition,
                record,
                lineage,
            )

        return evaluation

    @staticmethod
    def candidate_research_config(
        candidate: object,
        baseline_config: object,
    ) -> object:
        """Materialize a bounded research strategy candidate."""
        return CandidateImprovementEngine.materialize_strategy_config(
            candidate,  # type: ignore[arg-type]
            baseline_config,  # type: ignore[arg-type]
        )

    @staticmethod
    def validation_ready(bundle: ValidationBundle) -> bool:
        """Return whether all required validation gates are structurally ready."""
        return (
            bundle.integrity
            and bundle.leakage
            and bundle.oos
            and bundle.walk_forward
            and bundle.paper
            and bundle.reproducibility
            and not bundle.issues
        )

    def _persist_cycle(self, cycle: LearningCycle) -> None:
        """Persist cycle evidence when explicitly configured."""
        if self.cycle_store is not None:
            self.cycle_store.append(cycle)


__all__ = ["SelfLearningEngine", "SelfLearningRun"]
