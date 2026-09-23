import pytest

from execution.reconciliation import (
    BrokerPosition,
    BrokerReconciler,
    ReconciliationStatus,
)
from execution.readiness import LiveReadinessGate, LiveReadinessInput
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
