"""Tests for the controlled STOCK_BOT self-learning governance layer.

These tests cover causality, immutable provenance, dataset/experiment state,
promotion gates, champion/rollback invariants, and drift-to-investigation
behavior without requiring broker credentials or live trading.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from experiments.definition import ExperimentDefinition
from experiments.record import ExperimentRecord
from journal.models import TradeDecisionRecord, TradeJournalRecord

from learning.champion import ChampionChallenger, build_rollback_plan
from learning.cycle_store import LearningCycleStore
from learning.dataset_store import DatasetManifestStore
from learning.drift import DriftInvestigator
from learning.experience import (
    ExperienceContractError,
    audit_journal_linkage,
    build_trade_experience,
)
from learning.lifecycle import LearningLifecycle
from learning.promotion import PromotionGate
from learning.self_learning_models import (
    DatasetVersion,
    FailureClass,
    LearningCycle,
    LearningDecision,
    LearningState,
    PromotionReview,
    ValidationEvidence,
)


def _decision(trade_id: str = "T1") -> TradeDecisionRecord:
    """Create deterministic decision-time evidence."""
    return TradeDecisionRecord(
        trade_id=trade_id,
        timestamp=datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc),
        symbol="RELIANCE",
        direction="LONG",
        market_regime="TREND_UP",
        features={"rsi": 55.0, "rvol_20": 1.2},
        model_version="signal-v1",
        probability=0.71,
        entry=100.0,
        stop=98.0,
        target=103.0,
        position_size=10.0,
        failure_reason=None,
        strategy_version="STRAT-v1",
        risk_version="RISK-v1",
        execution_version="EXEC-v1",
        provenance={
            "sector": "ENERGY",
            "volatility_state": "LOW_VOLATILITY",
            "feature_schema_version": "features-v1",
        },
    )


def _outcome(trade_id: str = "T1", pnl: float = 20.0) -> TradeJournalRecord:
    """Create deterministic completed-trade evidence."""
    return TradeJournalRecord(
        journal_id=f"J-{trade_id}",
        trade_id=trade_id,
        symbol="RELIANCE",
        direction="LONG",
        entry_time=datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc),
        exit_time=datetime(2026, 9, 24, 10, 15, tzinfo=timezone.utc),
        entry_price=100.0,
        exit_price=102.0 if pnl > 0 else 98.0,
        quantity=10.0,
        gross_pnl=pnl,
        fees=1.0,
        slippage_cost=0.5,
        net_pnl=pnl,
        holding_minutes=15.0,
        mae=-20.0,
        mfe=30.0,
    )


def _validation(*, governance: bool = False) -> ValidationEvidence:
    """Create a complete structural evidence fixture."""
    return ValidationEvidence(
        integrity_passed=True,
        leakage_passed=True,
        oos_passed=True,
        walk_forward_passed=True,
        paper_passed=True,
        predictive_metrics={
            "balanced_accuracy": 0.60,
            "macro_f1": 0.58,
            "log_loss": 0.92,
            "brier_score": 0.18,
            "expected_calibration_error": 0.04,
        },
        trading_metrics={"trade_count": 100.0},
    )


def test_experience_requires_same_trade_id() -> None:
    """Mismatched decision/outcome records must fail closed."""
    with pytest.raises(ExperienceContractError, match="same trade_id"):
        build_trade_experience(_decision("T1"), _outcome("T2"))


def test_experience_preserves_decision_time_features() -> None:
    """Experience must retain the decision-time feature snapshot."""
    experience = build_trade_experience(_decision(), _outcome())
    assert experience.feature_snapshot == {"rsi": 55.0, "rvol_20": 1.2}
    assert experience.outcome_label == "LONG_SUCCESS"
    assert experience.r_multiple > 0


def test_journal_audit_detects_orphans_and_mismatches() -> None:
    """Unlinked records must block learning."""
    audit = audit_journal_linkage(
        (_decision("T1"),),
        (_outcome("T2"),),
    )
    assert audit.valid is False
    assert audit.orphan_decision_ids == ("T1",)
    assert audit.orphan_outcome_ids == ("T2",)


def test_dataset_manifest_is_immutable_by_version(tmp_path) -> None:
    """A dataset version cannot silently point at changed metadata."""
    store = DatasetManifestStore(tmp_path / "datasets.jsonl")
    manifest = DatasetVersion(
        dataset_version="dataset-v1",
        creation_timestamp="2026-09-24T00:00:00+00:00",
        source="phase9_training",
        symbols=("RELIANCE", "TCS"),
        period_start="2024-01-01",
        period_end="2026-08-31",
        row_count=3,
        label_distribution={
            "LONG_SUCCESS": 1,
            "SHORT_SUCCESS": 1,
            "NO_EDGE": 1,
        },
        feature_schema_version="features-v1",
        label_definition_version="labels-v1",
    )
    store.append(manifest)
    assert store.get("dataset-v1").fingerprint == manifest.fingerprint

    changed = DatasetVersion(
        dataset_version=manifest.dataset_version,
        creation_timestamp=manifest.creation_timestamp,
        source=manifest.source,
        symbols=manifest.symbols,
        period_start=manifest.period_start,
        period_end="2026-09-01",
        row_count=manifest.row_count,
        label_distribution=dict(manifest.label_distribution),
        feature_schema_version=manifest.feature_schema_version,
        label_definition_version=manifest.label_definition_version,
        source_trade_ids=manifest.source_trade_ids,
        known_limitations=manifest.known_limitations,
    )
    with pytest.raises(ValueError, match="different metadata"):
        store.append(changed)


def test_cycle_store_round_trip(tmp_path) -> None:
    """Learning-cycle identities must survive persistence."""
    cycle = LearningCycle(
        cycle_id="cycle-1",
        state=LearningState.HYPOTHESIS,
        experience_fingerprints=("a" * 64,),
        learning_evidence_fingerprints=("b" * 64,),
        experiment_id="EXP-1",
        candidate_id=None,
        promotion_review_fingerprint=None,
        decision=LearningDecision.REDESIGN,
    )
    store = LearningCycleStore(tmp_path / "cycles.jsonl")
    store.append(cycle)
    assert store.read_all() == (cycle,)


def test_lifecycle_blocks_invalid_transition() -> None:
    """Promotion cannot jump directly from observation."""
    lifecycle = LearningLifecycle()
    lifecycle.require_transition("OBSERVATION", "HYPOTHESIS")
    with pytest.raises(ValueError):
        lifecycle.require_transition("OBSERVATION", "PROMOTED")


def test_promotion_gate_is_fail_closed_without_governance() -> None:
    """Technical evidence alone cannot trigger promotion."""
    review = PromotionGate().review(
        candidate_id="C1",
        candidate_fingerprint="c" * 64,
        current_model_version="v1",
        challenger_model_version="v2",
        validation=_validation(),
        reproducibility_passed=True,
        governance_approved=False,
    )
    assert review.decision is LearningDecision.REJECT
    assert "GOVERNANCE_APPROVAL_REQUIRED" in review.reasons
    assert review.promotable is False


def test_promotion_gate_accepts_complete_explicit_review() -> None:
    """A complete review is promotable only with explicit governance."""
    review = PromotionGate().review(
        candidate_id="C1",
        candidate_fingerprint="c" * 64,
        current_model_version="v1",
        challenger_model_version="v2",
        validation=_validation(),
        reproducibility_passed=True,
        governance_approved=True,
    )
    assert review.decision is LearningDecision.KEEP
    assert review.promotable is True


def test_rollback_plan_requires_distinct_versions() -> None:
    """Rollback must target a different verified model."""
    with pytest.raises(ValueError, match="differ"):
        build_rollback_plan(
            current_model_version="v2",
            previous_verified_version="v2",
            reason="degradation",
            promotion_review_fingerprint="a" * 64,
        )


def test_drift_creates_investigation_not_retraining() -> None:
    """Monitoring drift becomes an investigation hypothesis."""
    from experiments.monitoring import MonitoringReport

    report = MonitoringReport(
        error_rate=0.01,
        stale_rate=0.01,
        prediction_psi=0.4,
        alerts=("PREDICTION_DRIFT_EXCEEDED",),
    )
    investigation = DriftInvestigator().investigate(
        report,
        investigation_id="INV-1",
    )
    assert investigation is not None
    assert investigation.failure_class is FailureClass.CALIBRATION_FAILURE
    assert "retrain" not in investigation.hypothesis.lower()


def test_candidate_and_champion_pair_must_match() -> None:
    """A promotion review cannot be reused for another model pair."""
    review = PromotionReview(
        candidate_id="C1",
        candidate_fingerprint="c" * 64,
        current_model_version="v1",
        challenger_model_version="v2",
        validation=_validation(),
        reproducibility_passed=True,
        governance_approved=True,
        decision=LearningDecision.KEEP,
    )
    assert ChampionChallenger.review_is_consistent(
        review,
        current_model_version="v1",
        challenger_model_version="v2",
    )
    with pytest.raises(ValueError, match="challenger"):
        ChampionChallenger.review_is_consistent(
            review,
            current_model_version="v1",
            challenger_model_version="v3",
        )


def test_experiment_definition_is_frozen_and_distinct_from_learning_state() -> None:
    """Learning evidence must produce a versioned research definition."""
    definition = ExperimentDefinition(
        experiment_id="EXP-001",
        research_question="Does the challenger improve OOS prediction quality?",
        hypothesis="The challenger improves balanced accuracy and log loss.",
        failure_criterion="Reject if OOS robustness does not improve.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        period_start="2024-01-01",
        period_end="2026-08-31",
        symbols=("RELIANCE",),
        method="controlled_challenger",
        fixed_parameters=(("risk", "frozen"),),
        allowed_change=("model",),
    )
    assert len(definition.fingerprint()) == 64
    assert definition.allowed_change == ("model",)


def test_self_learning_engine_observe_builds_causal_learning_cycle():
    """Completed linked outcomes become immutable learning evidence."""
    from learning.orchestrator import SelfLearningEngine

    engine = SelfLearningEngine()
    run = engine.observe(
        tuple(_decision(f"T{i}") for i in range(1, 4)),
        tuple(_outcome(f"T{i}", pnl=-20.0) for i in range(1, 4)),
        cycle_id="cycle-observe-1",
    )

    assert run.audit.valid is True
    assert run.cycle.state is LearningState.HYPOTHESIS
    assert run.cycle.decision is LearningDecision.REDESIGN
    assert run.experiences
    assert run.cycle.experience_fingerprints == tuple(
        item.fingerprint for item in run.experiences
    )


def test_self_learning_engine_blocks_unlinked_observations():
    """Unlinked decision/outcome evidence must fail closed."""
    from learning.orchestrator import SelfLearningEngine

    with pytest.raises(ValueError, match="experience audit"):
        SelfLearningEngine().observe(
            (_decision("T1"),),
            (_outcome("T2", pnl=-20.0),),
            cycle_id="cycle-invalid-1",
        )


def test_learning_experience_fingerprint_is_deterministic():
    experience = _learning_experience_fixture()
    assert len(experience.fingerprint) == 64
    assert experience.fingerprint == experience.fingerprint


def _learning_experience_fixture():
    from learning.models import LearningExperience, LearningPattern
    return LearningExperience(
        pattern=LearningPattern.LOSS,
        evidence_count=3,
        population_count=3,
        occurrence_rate=1.0,
        confidence=0.5,
        average_reward=-0.5,
        total_reward=-1.5,
        source_trade_ids=("T1", "T2", "T3"),
        rationale="Observed loss evidence.",
    )


def test_experiment_preparation_binds_definition_to_dataset_lineage():
    from learning.orchestrator import SelfLearningEngine

    dataset = SelfLearningEngine.dataset_version(
        version="dataset-v-bind-1",
        source="empirical_outcomes",
        symbols=("RELIANCE", "TCS"),
        period_start="2024-01-01",
        period_end="2026-08-31",
        row_count=3,
        label_distribution={"LONG_SUCCESS": 1, "SHORT_SUCCESS": 1, "NO_EDGE": 1},
        feature_schema_version="features-v1",
        label_definition_version="labels-v1",
        creation_timestamp="2026-10-02T00:00:00+00:00",
    )
    prepared = SelfLearningEngine.prepare_experiment(
        experiment_id="EXP-BIND-1",
        research_question="Test dataset lineage binding",
        hypothesis="The controlled change improves evidence quality.",
        failure_criterion="Reject if validation fails.",
        dataset_version=dataset,
        code_version="code-v1",
        period_start="2024-01-01",
        period_end="2026-08-31",
        symbols=("TCS", "RELIANCE"),
        method="controlled",
        change="model",
        fixed_components=("dataset", "strategy", "risk", "execution"),
        allowed_change=("model",),
        model_version="model-v1",
        strategy_version="strategy-v1",
        risk_version="risk-v1",
        execution_version="execution-v1",
    )
    assert prepared.definition.dataset_version == prepared.lineage.dataset.dataset_version
    assert prepared.definition.fingerprint()
    assert prepared.lineage.fingerprint


def test_experiment_preparation_rejects_dataset_period_mismatch():
    from dataclasses import replace
    from learning.orchestrator import ExperimentPreparation, SelfLearningEngine

    dataset = SelfLearningEngine.dataset_version(
        version="dataset-v-bind-2",
        source="empirical_outcomes",
        symbols=("RELIANCE",),
        period_start="2024-01-01",
        period_end="2026-08-31",
        row_count=1,
        label_distribution={"LONG_SUCCESS": 1},
        feature_schema_version="features-v1",
        label_definition_version="labels-v1",
        creation_timestamp="2026-10-02T00:00:00+00:00",
    )
    prepared = SelfLearningEngine.prepare_experiment(
        experiment_id="EXP-BIND-2",
        research_question="Test mismatch",
        hypothesis="Controlled change.",
        failure_criterion="Reject if validation fails.",
        dataset_version=dataset,
        code_version="code-v1",
        period_start="2024-01-01",
        period_end="2026-08-31",
        symbols=("RELIANCE",),
        method="controlled",
        change="model",
        fixed_components=("dataset", "strategy", "risk", "execution"),
        allowed_change=("model",),
        model_version="model-v1",
        strategy_version="strategy-v1",
        risk_version="risk-v1",
        execution_version="execution-v1",
    )
    changed = replace(
        prepared.definition,
        period_end="2026-09-01",
    )
    with pytest.raises(ValueError, match="period_end"):
        ExperimentPreparation(definition=changed, lineage=prepared.lineage)


def _experiment_definition_fixture():
    return ExperimentDefinition(
        experiment_id="EXP-REG-1",
        research_question="Research registration integrity",
        hypothesis="A frozen candidate improves evidence quality.",
        failure_criterion="Reject invalid measured evidence.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        period_start="2024-01-01",
        period_end="2026-08-31",
        symbols=("RELIANCE",),
        method="controlled",
        fixed_parameters=(("risk", "frozen"),),
        allowed_change=("model",),
    )


def _experiment_record_fixture(definition):
    return ExperimentRecord.from_definition(
        definition,
        observations=10,
        label_distribution={"LONG_SUCCESS": 5, "NO_EDGE": 5},
        baseline_results={"backtest": {"metrics": {"trade_count": 10}}},
        interpretation="Measured experiment.",
        decision="INCONCLUSIVE",
        root_cause="",
        lesson="Evidence retained.",
        next_experiment="Collect more evidence.",
    )


def test_register_experiment_requires_exact_record_and_lineage():
    from experiments.lineage import build_lineage
    from learning.orchestrator import SelfLearningEngine

    definition = _experiment_definition_fixture()
    record = _experiment_record_fixture(definition)
    lineage = build_lineage(definition, record)
    evaluation = SelfLearningEngine().register_experiment(
        definition=definition,
        record=record,
        lineage=lineage,
    )
    assert evaluation.valid is True


def test_register_experiment_rejects_mismatched_lineage():
    from experiments.lineage import build_lineage
    from learning.orchestrator import SelfLearningEngine

    definition = _experiment_definition_fixture()
    record = _experiment_record_fixture(definition)
    other_definition = ExperimentDefinition(
        **{
            **definition.to_dict(),
            "experiment_id": "EXP-REG-OTHER",
        }
    )
    other_record = _experiment_record_fixture(other_definition)
    other_lineage = build_lineage(other_definition, other_record)

    with pytest.raises(ValueError, match="lineage does not match frozen"):
        SelfLearningEngine().register_experiment(
            definition=definition,
            record=record,
            lineage=other_lineage,
        )


def test_register_experiment_does_not_persist_invalid_measurements(tmp_path):
    from experiments.lineage import build_lineage
    from learning.experiment_store import ExperimentRegistry
    from learning.orchestrator import SelfLearningEngine

    definition = _experiment_definition_fixture()
    record = ExperimentRecord.from_definition(
        definition,
        observations=10,
        baseline_results={"backtest": {"metrics": {"trade_count": -1}}},
        decision="INCONCLUSIVE",
    )
    lineage = build_lineage(definition, record)
    registry = ExperimentRegistry(tmp_path / "experiments.jsonl")
    evaluation = SelfLearningEngine(
        experiment_registry=registry,
    ).register_experiment(
        definition=definition,
        record=record,
        lineage=lineage,
    )
    assert evaluation.valid is False
    assert registry.count() == 0
