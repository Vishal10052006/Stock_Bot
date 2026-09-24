"""Controlled self-learning engine orchestrator.

The orchestrator composes existing Phase 16-20 contracts. It can consume
completed trade evidence, create a bounded experiment definition, retrain a
research candidate, assemble explicit validation evidence, and produce a
promotion review. It never executes trades or silently changes hard controls.

The caller supplies actual backtest/OOS/walk-forward/paper evidence; the
orchestrator never invents those measurements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Iterable, Mapping

from analysis import ErrorAnalysisReport, TradeErrorAnalyzer
from candidate_improvement.engine import CandidateImprovementEngine
from experiments.definition import ExperimentDefinition
from experiments.evaluation import EvaluationReport, evaluate_experiment_record
from experiments.lineage import LineageRecord, build_lineage
from experiments.record import ExperimentRecord
from journal.models import TradeDecisionRecord, TradeJournalRecord
from ml.model_registry import ModelRegistry

from .cycle_store import LearningCycleStore
from .engine import LearningEngine
from .experiment_store import ExperimentRegistry
from .promotion import PromotionGate
from .self_learning_models import (
    DatasetVersion,
    ExperimentLineage,
    LearningCycle,
    LearningDecision,
    LearningState,
    PromotionReview,
    ValidationEvidence,
)
from .validation import ValidationBundle, ValidationOrchestrator


@dataclass(frozen=True, slots=True)
class SelfLearningRun:
    """Immutable evidence result for one learning observation cycle."""

    cycle: LearningCycle
    audit: object
    analysis: ErrorAnalysisReport
    learning_report: object
    experiences: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class ExperimentPreparation:
    """Frozen inputs for one controlled learning experiment."""

    definition: ExperimentDefinition
    lineage: ExperimentLineage


class SelfLearningEngine:
    """Evidence-first coordinator for the complete self-learning lifecycle."""

    def __init__(
        self,
        *,
        learning_engine: LearningEngine | None = None,
        experiment_registry: ExperimentRegistry | None = None,
        cycle_store: LearningCycleStore | None = None,
        model_registry: ModelRegistry | None = None,
        promotion_gate: PromotionGate | None = None,
        validation_orchestrator: ValidationOrchestrator | None = None,
    ) -> None:
        self.learning_engine = learning_engine or LearningEngine()
        self.experiment_registry = experiment_registry
        self.cycle_store = cycle_store
        self.model_registry = model_registry
        self.promotion_gate = promotion_gate or PromotionGate()
        self.validation_orchestrator = (
            validation_orchestrator or ValidationOrchestrator()
        )

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
            experiences=experiences,
        )

    @staticmethod
    def dataset_version(
        *,
        version: str,
        source: str,
        symbols: Iterable[str],
        period_start: str,
        period_end: str,
        row_count: int,
        label_distribution: Mapping[str, int],
        feature_schema_version: str,
        label_definition_version: str,
        source_trade_ids: Iterable[str] = (),
        known_limitations: Iterable[str] = (),
        creation_timestamp: str | None = None,
    ) -> DatasetVersion:
        """Create an immutable dataset manifest without writing data."""
        return DatasetVersion(
            dataset_version=version,
            creation_timestamp=creation_timestamp
            or datetime.now(timezone.utc).isoformat(),
            source=source,
            symbols=tuple(symbols),
            period_start=period_start,
            period_end=period_end,
            row_count=row_count,
            label_distribution=dict(label_distribution),
            feature_schema_version=feature_schema_version,
            label_definition_version=label_definition_version,
            source_trade_ids=tuple(source_trade_ids),
            known_limitations=tuple(known_limitations),
        )

    @staticmethod
    def prepare_experiment(
        *,
        experiment_id: str,
        research_question: str,
        hypothesis: str,
        failure_criterion: str,
        dataset_version: DatasetVersion,
        code_version: str,
        period_start: str,
        period_end: str,
        symbols: Iterable[str],
        method: str,
        change: str,
        fixed_components: Iterable[str],
        allowed_change: Iterable[str],
        model_version: str,
        strategy_version: str,
        risk_version: str,
        execution_version: str,
        parent_experiment_id: str | None = None,
    ) -> ExperimentPreparation:
        """Freeze experiment methodology and complete reproducibility lineage."""
        allowed = tuple(sorted(set(allowed_change)))
        definition = ExperimentDefinition(
            experiment_id=experiment_id,
            research_question=research_question,
            hypothesis=hypothesis,
            failure_criterion=failure_criterion,
            dataset_version=dataset_version.dataset_version,
            code_version=code_version,
            period_start=period_start,
            period_end=period_end,
            symbols=tuple(sorted(set(symbols))),
            method=method,
            fixed_parameters=(
                ("change", change),
                ("feature_version", dataset_version.feature_schema_version),
                ("label_version", dataset_version.label_definition_version),
            ),
            allowed_change=allowed,
        )
        lineage = ExperimentLineage(
            experiment_id=experiment_id,
            dataset=dataset_version,
            code_version=code_version,
            feature_version=dataset_version.feature_schema_version,
            label_version=dataset_version.label_definition_version,
            model_version=model_version,
            strategy_version=strategy_version,
            risk_version=risk_version,
            execution_version=execution_version,
            change=change,
            fixed_components=tuple(fixed_components),
            parent_experiment_id=parent_experiment_id,
        )
        return ExperimentPreparation(definition=definition, lineage=lineage)

    def register_experiment(
        self,
        *,
        definition: ExperimentDefinition,
        record: ExperimentRecord,
        lineage: LineageRecord,
    ) -> EvaluationReport:
        """Validate and persist one completed experiment result."""
        evaluation = evaluate_experiment_record(record)
        if self.experiment_registry is not None:
            self.experiment_registry.append(definition, record, lineage)
        return evaluation

    def assemble_validation(
        self,
        *,
        integrity_passed: bool,
        leakage_passed: bool,
        oos_passed: bool,
        walk_forward_passed: bool,
        paper_passed: bool,
        reproducibility_passed: bool,
        predictive_metrics: Mapping[str, float] | None = None,
        trading_metrics: Mapping[str, float] | None = None,
        regime_metrics: Mapping[str, Mapping[str, float]] | None = None,
        symbol_metrics: Mapping[str, Mapping[str, float]] | None = None,
        date_metrics: Mapping[str, Mapping[str, float]] | None = None,
        effective_sample_diagnostics: object | None = None,
        structural_evaluation: EvaluationReport | None = None,
    ) -> ValidationBundle:
        """Assemble explicit promotion evidence from actual gate outputs."""
        return self.validation_orchestrator.assemble(
            integrity_passed=integrity_passed,
            leakage_passed=leakage_passed,
            oos_passed=oos_passed,
            walk_forward_passed=walk_forward_passed,
            paper_passed=paper_passed,
            reproducibility_passed=reproducibility_passed,
            predictive_metrics=predictive_metrics,
            trading_metrics=trading_metrics,
            regime_metrics=regime_metrics,
            symbol_metrics=symbol_metrics,
            date_metrics=date_metrics,
            effective_sample_diagnostics=effective_sample_diagnostics,
            structural_evaluation=structural_evaluation,
        )

    def review_promotion(
        self,
        *,
        candidate_id: str,
        candidate_fingerprint: str,
        current_model_version: str,
        challenger_model_version: str,
        validation: ValidationEvidence,
        reproducibility_passed: bool,
        governance_approved: bool = False,
        decision: LearningDecision | None = None,
    ) -> PromotionReview:
        """Create a deterministic promotion review; no activation occurs."""
        return self.promotion_gate.review(
            candidate_id=candidate_id,
            candidate_fingerprint=candidate_fingerprint,
            current_model_version=current_model_version,
            challenger_model_version=challenger_model_version,
            validation=validation,
            reproducibility_passed=reproducibility_passed,
            governance_approved=governance_approved,
            decision=decision,
        )

    @staticmethod
    def candidate_research_config(
        candidate: object,
        baseline_config: object,
    ) -> object:
        """Materialize a whitelisted research strategy candidate."""
        return CandidateImprovementEngine.materialize_strategy_config(
            candidate,  # type: ignore[arg-type]
            baseline_config,  # type: ignore[arg-type]
        )

    def _persist_cycle(self, cycle: LearningCycle) -> None:
        """Persist cycle evidence when an append-only store is configured."""
        if self.cycle_store is not None:
            self.cycle_store.append(cycle)


__all__ = [
    "ExperimentPreparation",
    "SelfLearningEngine",
    "SelfLearningRun",
]
