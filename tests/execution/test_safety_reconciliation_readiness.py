import pandas as pd
import pytest

from experiments.paper_evidence import PaperEvidenceSnapshot
from experiments.paper_journal import PaperEvidenceRecord
from experiments.paper_quality import assess_paper_evidence
from experiments.monitoring import MonitoringReport
from trading.risk.engine import RiskConfig

from backtesting.engine import BacktestResult
from backtesting.oos import OOSReport
from backtesting.walk_forward import WalkForwardTradingReport, WalkForwardWindow

from execution.reconciliation import (
    BrokerPosition,
    BrokerReconciler,
    ReconciliationStatus,
)
from execution.readiness import LiveReadinessGate, LiveReadinessInput, ReadinessEvidence
from execution.safety import (
    IndependentSafetyGate,
    SafetyBlock,
    SafetyState,
)


def test_independent_kill_switch_blocks() -> None:
    result = IndependentSafetyGate().evaluate(
        SafetyState(kill_switch_active=True)
    )
    assert not result.allowed
    assert result.block is SafetyBlock.KILL_SWITCH


def test_live_execution_remains_locked_by_default() -> None:
    result = IndependentSafetyGate().evaluate(SafetyState())
    assert not result.allowed
    assert result.block is SafetyBlock.LIVE_LOCKED


def test_reconciliation_matches_normalized_positions() -> None:
    report = BrokerReconciler().reconcile(
        (BrokerPosition("itc", 10, 100.0),),
        (BrokerPosition("ITC", 10, 100.0),),
    )
    assert report.status is ReconciliationStatus.MATCH
    assert report.safe


def test_reconciliation_blocks_on_mismatch() -> None:
    report = BrokerReconciler().reconcile(
        (BrokerPosition("ITC", 10, 100.0),),
        (BrokerPosition("ITC", 9, 100.0),),
    )
    assert report.status is ReconciliationStatus.MISMATCH
    assert not report.safe


def test_readiness_gate_fails_closed() -> None:
    gates = LiveReadinessInput(
        historical_data_validated=True,
        indicators_validated=True,
        features_leakage_safe=True,
        labels_validated=True,
        baseline_validated=True,
        model_validated=True,
        realistic_backtest_validated=True,
        leakage_audit_passed=True,
        oos_validated=True,
        walk_forward_validated=True,
        paper_evidence_validated=True,
        risk_controls_validated=True,
        monitoring_validated=True,
        kill_switch_validated=False,
        broker_integration_validated=False,
        reconciliation_validated=False,
        compliance_verified_current=False,
    )
    report = LiveReadinessGate().evaluate(gates)

    assert not report.ready
    assert "kill_switch_validated" in report.failed_gates
    assert "broker_integration_validated" in report.failed_gates
    assert "reconciliation_validated" in report.failed_gates
    assert "compliance_verified_current" in report.failed_gates


def test_duplicate_broker_positions_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        BrokerReconciler().reconcile(
            (
                BrokerPosition("ITC", 10, 100.0),
                BrokerPosition("ITC", 5, 101.0),
            ),
            (),
        )


def test_reconciliation_blocks_when_snapshot_is_missing() -> None:
    report = BrokerReconciler().reconcile(None, ())

    assert report.status is ReconciliationStatus.BLOCKED
    assert not report.safe


def _valid_paper_quality():
    snapshot = PaperEvidenceSnapshot(
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-v1",
        code_version="code-v1",
        signal_count=10,
        fill_count=8,
        slippage_observation_count=8,
        latency_observation_count=8,
        false_signal_count=1,
        drawdown_observation_count=8,
        regime_observation_count=8,
        calibration_observation_count=8,
        operational_event_count=8,
        operational_error_count=1,
        stale_event_count=0,
    )
    record = PaperEvidenceRecord.create(
        evidence=snapshot,
        period_start="2026-09-21T09:15:00+00:00",
        period_end="2026-09-21T15:30:00+00:00",
        source_run_id="readiness-test",
    )
    return assess_paper_evidence((record,))


def test_readiness_accepts_structurally_valid_paper_quality() -> None:
    gates = LiveReadinessInput(
        historical_data_validated=True,
        indicators_validated=True,
        features_leakage_safe=True,
        labels_validated=True,
        baseline_validated=True,
        model_validated=True,
        realistic_backtest_validated=True,
        leakage_audit_passed=True,
        oos_validated=True,
        walk_forward_validated=True,
        paper_evidence_validated=True,
        risk_controls_validated=True,
        monitoring_validated=True,
        kill_switch_validated=True,
        broker_integration_validated=True,
        reconciliation_validated=True,
        compliance_verified_current=True,
    )
    report = LiveReadinessGate().evaluate(
        gates,
        paper_evidence_quality=_valid_paper_quality(),
    )

    assert report.ready


def test_readiness_blocks_invalid_paper_quality() -> None:
    gates = LiveReadinessInput(
        historical_data_validated=True,
        indicators_validated=True,
        features_leakage_safe=True,
        labels_validated=True,
        baseline_validated=True,
        model_validated=True,
        realistic_backtest_validated=True,
        leakage_audit_passed=True,
        oos_validated=True,
        walk_forward_validated=True,
        paper_evidence_validated=True,
        risk_controls_validated=True,
        monitoring_validated=True,
        kill_switch_validated=True,
        broker_integration_validated=True,
        reconciliation_validated=True,
        compliance_verified_current=True,
    )
    invalid = assess_paper_evidence(())
    report = LiveReadinessGate().evaluate(
        gates,
        paper_evidence_quality=invalid,
    )

    assert not report.ready
    assert "paper_evidence_quality_validated" in report.failed_gates



def test_readiness_provenance_fails_closed_when_required() -> None:
    gates = LiveReadinessInput(
        historical_data_validated=True,
        indicators_validated=True,
        features_leakage_safe=True,
        labels_validated=True,
        baseline_validated=True,
        model_validated=True,
        realistic_backtest_validated=True,
        leakage_audit_passed=True,
        oos_validated=True,
        walk_forward_validated=True,
        paper_evidence_validated=True,
        risk_controls_validated=True,
        monitoring_validated=True,
        kill_switch_validated=True,
        broker_integration_validated=True,
        reconciliation_validated=True,
        compliance_verified_current=True,
    )
    report = LiveReadinessGate().evaluate(gates, require_provenance=True)

    assert not report.ready
    assert "historical_data_validated_provenance" in report.failed_gates


def test_readiness_accepts_complete_gate_provenance() -> None:
    gates = LiveReadinessInput(
        historical_data_validated=True,
        indicators_validated=True,
        features_leakage_safe=True,
        labels_validated=True,
        baseline_validated=True,
        model_validated=True,
        realistic_backtest_validated=True,
        leakage_audit_passed=True,
        oos_validated=True,
        walk_forward_validated=True,
        paper_evidence_validated=True,
        risk_controls_validated=True,
        monitoring_validated=True,
        kill_switch_validated=True,
        broker_integration_validated=True,
        reconciliation_validated=True,
        compliance_verified_current=True,
    )
    evidence_kinds = {
        "historical_data_validated": "validation",
        "indicators_validated": "validation",
        "features_leakage_safe": "audit",
        "labels_validated": "validation",
        "baseline_validated": "experiment_lineage",
        "model_validated": "experiment_lineage",
        "realistic_backtest_validated": "backtest",
        "leakage_audit_passed": "audit",
        "oos_validated": "oos",
        "walk_forward_validated": "walk_forward",
        "paper_evidence_validated": "paper_evidence",
        "risk_controls_validated": "risk",
        "monitoring_validated": "monitoring",
        "kill_switch_validated": "safety",
        "broker_integration_validated": "broker",
        "reconciliation_validated": "reconciliation",
        "compliance_verified_current": "compliance",
    }

    evidence = tuple(
        ReadinessEvidence(
            gate=field,
            artifact_fingerprint="a" * 64,
            dataset_version="dataset-v1",
            code_version="code-v1",
            validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
            source="test",
            evidence_kind=evidence_kinds[field],
        )
        for field in LiveReadinessGate._FIELDS
    )
    report = LiveReadinessGate().evaluate(
        gates,
        evidence=evidence,
        require_provenance=True,
    )

    assert report.ready
    assert len({item.fingerprint for item in evidence}) == len(evidence)


def test_readiness_evidence_can_bind_existing_lineage() -> None:
    from experiments.lineage import LineageRecord

    lineage = LineageRecord(
        experiment_id="EXP-1",
        definition_fingerprint="a" * 64,
        record_fingerprint="b" * 64,
        dataset_version="dataset-v1",
        code_version="code-v1",
    ).with_computed_id()

    evidence = ReadinessEvidence.from_lineage(
        lineage,
        gate="oos_validated",
        validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
    )

    assert evidence.artifact_fingerprint == lineage.computed_id()
    assert evidence.dataset_version == "dataset-v1"
    assert evidence.code_version == "code-v1"
    assert evidence.source == f"lineage:{lineage.computed_id()}"


def test_readiness_rejects_tampered_lineage_id() -> None:
    from experiments.lineage import LineageRecord

    lineage = LineageRecord(
        experiment_id="EXP-1",
        definition_fingerprint="a" * 64,
        record_fingerprint="b" * 64,
        dataset_version="dataset-v1",
        code_version="code-v1",
        lineage_id="c" * 64,
    )

    with pytest.raises(ValueError, match="does not match"):
        ReadinessEvidence.from_lineage(
            lineage,
            gate="oos_validated",
            validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
        )


def test_readiness_evidence_binds_existing_artifact_fingerprint() -> None:
    artifacts = (
        (
            _valid_paper_quality(),
            "paper_evidence_validated",
            "paper_evidence",
        ),
        (
            MonitoringReport(
                error_rate=0.01,
                stale_rate=0.01,
                prediction_psi=0.05,
                alerts=(),
            ),
            "monitoring_validated",
            "monitoring",
        ),
        (
            BrokerReconciler().reconcile(
                (BrokerPosition("ITC", 10, 100.0),),
                (BrokerPosition("ITC", 10, 100.0),),
            ),
            "reconciliation_validated",
            "reconciliation",
        ),
        (
            IndependentSafetyGate().evaluate(
                SafetyState(live_execution_enabled=False)
            ),
            "kill_switch_validated",
            "safety",
        ),
        (
            RiskConfig(),
            "risk_controls_validated",
            "risk",
        ),
    )

    for artifact, gate, kind in artifacts:
        evidence = ReadinessEvidence.from_artifact(
            artifact,
            gate=gate,
            evidence_kind=kind,
            dataset_version="dataset-v1",
            code_version="code-v1",
            validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
            source="test",
        )
        assert evidence.artifact_fingerprint == artifact.fingerprint
        assert evidence.evidence_kind == kind


def test_readiness_artifact_binding_rejects_wrong_kind() -> None:
    with pytest.raises(ValueError, match="invalid evidence_kind"):
        ReadinessEvidence.from_artifact(
            MonitoringReport(
                error_rate=0.01,
                stale_rate=0.01,
                prediction_psi=0.05,
                alerts=(),
            ),
            gate="monitoring_validated",
            evidence_kind="risk",
            dataset_version="dataset-v1",
            code_version="code-v1",
            validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
            source="test",
        )


def _provenance_evidence(gate: str) -> ReadinessEvidence:
    kind = {
        "historical_data_validated": "validation",
        "indicators_validated": "validation",
        "features_leakage_safe": "audit",
        "labels_validated": "validation",
        "baseline_validated": "experiment_lineage",
        "model_validated": "experiment_lineage",
        "realistic_backtest_validated": "backtest",
        "leakage_audit_passed": "audit",
        "oos_validated": "oos",
        "walk_forward_validated": "walk_forward",
        "paper_evidence_validated": "paper_evidence",
        "risk_controls_validated": "risk",
        "monitoring_validated": "monitoring",
        "kill_switch_validated": "safety",
        "broker_integration_validated": "broker",
        "reconciliation_validated": "reconciliation",
        "compliance_verified_current": "compliance",
    }.get(gate, "validation")
    return ReadinessEvidence(
        gate=gate,
        artifact_fingerprint="a" * 64,
        dataset_version="dataset-v1",
        code_version="code-v1",
        validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
        source="test",
        evidence_kind=kind,
    )


def test_readiness_rejects_unknown_provenance_gate() -> None:
    with pytest.raises(ValueError, match="unknown readiness evidence gate"):
        LiveReadinessGate().evaluate(
            LiveReadinessInput(**{field: True for field in LiveReadinessGate._FIELDS}),
            evidence=(_provenance_evidence("unknown_gate"),),
            require_provenance=True,
        )


def test_readiness_rejects_duplicate_provenance_gate() -> None:
    evidence = _provenance_evidence("oos_validated")
    with pytest.raises(ValueError, match="duplicate readiness evidence gate"):
        LiveReadinessGate().evaluate(
            LiveReadinessInput(**{field: True for field in LiveReadinessGate._FIELDS}),
            evidence=(evidence, evidence),
            require_provenance=True,
        )


def test_readiness_rejects_wrong_provenance_kind() -> None:
    evidence = _provenance_evidence("oos_validated")
    evidence = ReadinessEvidence(
        gate=evidence.gate,
        artifact_fingerprint=evidence.artifact_fingerprint,
        dataset_version=evidence.dataset_version,
        code_version=evidence.code_version,
        validated_at=evidence.validated_at,
        source=evidence.source,
        evidence_kind="risk",
    )
    with pytest.raises(ValueError, match="invalid evidence_kind"):
        LiveReadinessGate().evaluate(
            LiveReadinessInput(**{field: True for field in LiveReadinessGate._FIELDS}),
            evidence=(evidence,),
            require_provenance=True,
        )


def test_readiness_rejects_malformed_provenance_fingerprint() -> None:
    evidence = ReadinessEvidence(
        gate="oos_validated",
        artifact_fingerprint="not-a-sha",
        dataset_version="dataset-v1",
        code_version="code-v1",
        validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
        source="test",
    )
    with pytest.raises(ValueError, match="SHA-256"):
        LiveReadinessGate().evaluate(
            LiveReadinessInput(**{field: True for field in LiveReadinessGate._FIELDS}),
            evidence=(evidence,),
            require_provenance=True,
        )


def test_readiness_evidence_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ReadinessEvidence(
            gate="historical_data_validated",
            artifact_fingerprint="artifact",
            dataset_version="dataset-v1",
            code_version="code-v1",
            validated_at=pd.Timestamp("2026-09-23T10:00:00").to_pydatetime(),
            source="test",
        )


def test_readiness_binds_research_artifact_fingerprints() -> None:
    timestamp = pd.Timestamp("2026-09-23T10:00:00Z")
    oos = OOSReport(
        train_rows=10,
        validation_rows=5,
        test_rows=5,
        train_end=timestamp - pd.Timedelta(minutes=20),
        validation_end=timestamp - pd.Timedelta(minutes=10),
        test_start=timestamp,
        predictions=pd.Series(["LONG_SUCCESS"]),
        test_data=pd.DataFrame(
            {
                "timestamp": [timestamp],
                "feature": [1.0],
            }
        ),
    )
    walk_forward = WalkForwardTradingReport(
        windows=(
            WalkForwardWindow(
                fold_id=1,
                train_start=timestamp - pd.Timedelta(hours=2),
                train_end=timestamp - pd.Timedelta(hours=1),
                test_start=timestamp - pd.Timedelta(minutes=30),
                test_end=timestamp,
                train_rows=10,
                test_rows=5,
                purged_rows=1,
            ),
        ),
        results=(5,),
    )
    backtest = BacktestResult(steps=(), outcomes=())

    for artifact, gate, kind in (
        (oos, "oos_validated", "oos"),
        (walk_forward, "walk_forward_validated", "walk_forward"),
        (backtest, "realistic_backtest_validated", "backtest"),
    ):
        evidence = ReadinessEvidence.from_artifact(
            artifact,
            gate=gate,
            evidence_kind=kind,
            dataset_version="dataset-v1",
            code_version="code-v1",
            validated_at=timestamp.to_pydatetime(),
            source="research-test",
        )
        assert evidence.artifact_fingerprint == artifact.fingerprint
        assert len(evidence.artifact_fingerprint) == 64


def test_research_artifact_fingerprints_are_deterministic() -> None:
    timestamp = pd.Timestamp("2026-09-23T10:00:00Z")
    first = WalkForwardTradingReport(
        windows=(
            WalkForwardWindow(
                fold_id=1,
                train_start=timestamp - pd.Timedelta(hours=2),
                train_end=timestamp - pd.Timedelta(hours=1),
                test_start=timestamp - pd.Timedelta(minutes=30),
                test_end=timestamp,
                train_rows=10,
                test_rows=5,
                purged_rows=1,
            ),
        ),
        results=(5,),
    )
    second = WalkForwardTradingReport(
        windows=first.windows,
        results=first.results,
    )

    assert first.fingerprint == second.fingerprint
