"""Fail-closed controlled-deployment readiness boundary.

Phase 26 is a governance/deployment boundary, not a broker activator.
It converts the existing live-readiness evidence into an auditable
deployment-review decision while preserving the repository's live lock.

No function in this module submits, enables, or authorizes a broker order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from execution.readiness import LiveReadinessReport


class DeploymentBlocked(RuntimeError):
    """Raised when a controlled deployment review is not eligible."""


@dataclass(frozen=True, slots=True)
class DeploymentReview:
    """Immutable Phase-26 deployment review result."""

    reviewed_at: datetime
    readiness_ready: bool
    human_approval: bool
    broker_verified: bool
    compliance_current: bool
    live_lock_active: bool
    activation_allowed: bool
    status: str
    failed_gates: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if self.status not in {"BLOCKED", "READY_FOR_REVIEW"}:
            raise ValueError("invalid deployment review status")
        if self.activation_allowed:
            raise ValueError("Phase 26 cannot authorize live activation")

    def canonical_json(self) -> str:
        payload = {
            "reviewed_at": self.reviewed_at.isoformat(),
            "readiness_ready": self.readiness_ready,
            "human_approval": self.human_approval,
            "broker_verified": self.broker_verified,
            "compliance_current": self.compliance_current,
            "live_lock_active": self.live_lock_active,
            "activation_allowed": self.activation_allowed,
            "status": self.status,
            "failed_gates": list(self.failed_gates),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ControlledDeploymentGate:
    """Evaluate Phase-26 prerequisites without enabling live execution."""

    def review(
        self,
        readiness: LiveReadinessReport,
        *,
        reviewed_at: datetime,
        human_approval: bool,
        broker_verified: bool,
        compliance_current: bool,
        live_lock_active: bool = True,
    ) -> DeploymentReview:
        if not isinstance(readiness, LiveReadinessReport):
            raise TypeError("readiness must be LiveReadinessReport")
        if reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        for name, value in {
            "human_approval": human_approval,
            "broker_verified": broker_verified,
            "compliance_current": compliance_current,
            "live_lock_active": live_lock_active,
        }.items():
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be bool")

        failed = list(readiness.failed_gates)
        if not human_approval:
            failed.append("human_approval")
        if not broker_verified:
            failed.append("broker_verification")
        if not compliance_current:
            failed.append("compliance_current")
        if live_lock_active:
            failed.append("live_execution_lock")

        status = "BLOCKED" if failed else "READY_FOR_REVIEW"

        # Deliberately hard-coded false: this object is evidence for a future
        # controlled deployment process, never a live-order authorization.
        return DeploymentReview(
            reviewed_at=reviewed_at,
            readiness_ready=readiness.ready,
            human_approval=human_approval,
            broker_verified=broker_verified,
            compliance_current=compliance_current,
            live_lock_active=live_lock_active,
            activation_allowed=False,
            status=status,
            failed_gates=tuple(dict.fromkeys(failed)),
        )


def require_review_ready(review: DeploymentReview) -> None:
    """Fail closed unless all review prerequisites are satisfied.

    Even a review-ready result cannot authorize live execution.
    """
    if not isinstance(review, DeploymentReview):
        raise TypeError("review must be DeploymentReview")
    if review.status != "READY_FOR_REVIEW":
        raise DeploymentBlocked(
            "controlled deployment review is blocked: "
            + ", ".join(review.failed_gates)
        )
    raise DeploymentBlocked(
        "Phase 26 review is complete, but live activation remains locked"
    )


__all__ = [
    "ControlledDeploymentGate",
    "DeploymentBlocked",
    "DeploymentReview",
    "require_review_ready",
]
