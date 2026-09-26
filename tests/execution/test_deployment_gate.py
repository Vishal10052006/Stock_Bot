from datetime import datetime, timezone

import pytest

from execution.deployment_gate import (
    ControlledDeploymentGate,
    DeploymentBlocked,
    require_review_ready,
)
from execution.readiness import LiveReadinessReport


def _readiness(ready: bool) -> LiveReadinessReport:
    return LiveReadinessReport(
        ready=ready,
        failed_gates=() if ready else ("paper_evidence_validated",),
    )


def test_phase26_blocks_missing_prerequisites() -> None:
    review = ControlledDeploymentGate().review(
        _readiness(False),
        reviewed_at=datetime.now(timezone.utc),
        human_approval=False,
        broker_verified=False,
        compliance_current=False,
    )

    assert review.status == "BLOCKED"
    assert review.activation_allowed is False
    assert "paper_evidence_validated" in review.failed_gates
    assert "human_approval" in review.failed_gates
    assert "broker_verification" in review.failed_gates
    assert "compliance_current" in review.failed_gates
    assert "live_execution_lock" in review.failed_gates


def test_phase26_ready_review_still_cannot_activate() -> None:
    review = ControlledDeploymentGate().review(
        _readiness(True),
        reviewed_at=datetime.now(timezone.utc),
        human_approval=True,
        broker_verified=True,
        compliance_current=True,
        live_lock_active=False,
    )

    assert review.status == "READY_FOR_REVIEW"
    assert review.activation_allowed is False

    with pytest.raises(DeploymentBlocked, match="remains locked"):
        require_review_ready(review)


def test_phase26_live_lock_is_default_and_fail_closed() -> None:
    review = ControlledDeploymentGate().review(
        _readiness(True),
        reviewed_at=datetime.now(timezone.utc),
        human_approval=True,
        broker_verified=True,
        compliance_current=True,
    )

    assert review.status == "BLOCKED"
    assert review.live_lock_active is True
    assert review.activation_allowed is False


def test_phase26_review_is_deterministically_fingerprinted() -> None:
    timestamp = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    gate = ControlledDeploymentGate()

    first = gate.review(
        _readiness(True),
        reviewed_at=timestamp,
        human_approval=True,
        broker_verified=True,
        compliance_current=True,
        live_lock_active=False,
    )
    second = gate.review(
        _readiness(True),
        reviewed_at=timestamp,
        human_approval=True,
        broker_verified=True,
        compliance_current=True,
        live_lock_active=False,
    )

    assert first.fingerprint == second.fingerprint
