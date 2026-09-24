"""Tests for the controlled STOCK_BOT self-learning governance layer.

These tests focus on invariants that can be checked without live data, broker
credentials, or real-money execution.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from journal.models import TradeDecisionRecord, TradeJournalRecord

from learning.champion import ChampionChallenger, build_rollback_plan
from learning.cycle_store import LearningCycleStore
from learning.dataset_store import DatasetManifestStore
from learning.drift import DriftInvestigator
from learning.engine import LearningEngine
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
    LearningDecision,
    LearningState,
    LearningCycle,
    PromotionReview,
    ValidationEvidence,
)


def _decision(trade_id: str = "T1") -> TradeDecisionRecord:
    """Create a deterministic decision-time fixture."""
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
    """Create a deterministic completed-trade fixture."""
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


def test_experience_requires_same_trade_id() -> None:
    """Mismatched decision/outcome records must fail closed."""
    with pytest.raises(ExperienceContractError, match="same trade_id"):
        build_trade_experience(_decision("T1"), _outcome("T2"))


def test_experience_preserves_decision_time_features() -> None:
    """Experience must retain only the decision feature snapshot."""
    experience = build_trade_experience(_decision(), _outcome())
    assert experience.feature_snapshot == {"rsi": 55.0, "rvol_20": 1.2}
    assert experience.outcome_label == "LONG_SUCCESS"
    assert experience.r_multiple > 0


def test_journal_audit_detects_orphans_and_mismatches() -> None:
    """Unlinked records and contradictory facts must be visible."""
    audit = audit_journal_linkage(
        (_decision("T1"),),
        (_outcome("T2"),),
    )
    assert audit.valid is False
    assert audit.orphan_decision_ids == ("T1",)
    assert audit.orphan_outcome_ids == ("T2",)


def test_dataset_manifest_is_immutable_by_version(tmp_path) -> None:
    """A version may not silently point to different metadata."""
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

    with pytest.raises(ValueError, match="different metadata"):
        store.append(
            DatasetVersion(
                **{
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
                }
            )
        )


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
    loaded = store.read_all()
    assert loaded == (cycle,)


def test_lifecycle_blocks_invalid_transition() -> None:
    """Promotion cannot jump over the required research gates."""
    lifecycle = LearningLifecycle()
    lifecycle.require_transition("OBSERVATION", "HYPOTHESIS")
    with pytest.raises(ValueError):
        lifecycle.require_transition("OBSERVATION", "PROMOTED")


def test_promotion_gate_is_fail_closed_without_governance() -> None:
    """Even complete technical evidence cannot auto-promote."""
    evidence = ValidationEvidence(
        integrity_passed=True,
        leakage_passed=True,
        oos_passed=True,
        walk_forward_passed=True,
        paper_passed=True,
    )
    review = PromotionGate().review(
        candidate_id="C1",
        candidate_fingerprint="c" * 64,
        current_model_version="v1",
        challenger_model_version="v2",
        validation=evidence,
        reproducibility_passed=True,
        governance_approved=False,
    )
    assert review.decision is LearningDecision.REJECT
    assert "GOVERNANCE_APPROVAL_REQUIRED" in review.reasons
    assert review.promotable is False


def test_promotion_gate_accepts_explicit_governance_evidence() -> None:
    """A review is promotable only when every required gate is satisfied."""
    evidence = ValidationEvidence(
        integrity_passed=True,
        leakage_passed=True,
        oos_passed=True,
        walk_forward_passed=True,
        paper_passed=True,
    )
    review = PromotionGate().review(
        candidate_id="C1",
        candidate_fingerprint="c" * 64,
        current_model_version="v1",
        challenger_model_version="v2",
        validation=evidence,
        reproducibility_passed=True,
        governance_approved=True,
    )
    assert review.decision is LearningDecision.KEEP
    assert review.promotable is True


def test_rollback_plan_requires_distinct_versions() -> None:
    """Rollback must point to a different verified version."""
    with pytest.raises(ValueError, match="differ"):
        build_rollback_plan(
            current_model_version="v2",
            previous_verified_version="v2",
            reason="degradation",
            promotion_review_fingerprint="a" * 64,
        )


def test_drift_creates_investigation_not_retraining() -> None:
    """Monitoring drift becomes a hypothesis rather than auto-retraining."""
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
