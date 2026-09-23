"""Execution safety and readiness boundaries."""

from .readiness import LiveReadinessGate, LiveReadinessInput, LiveReadinessReport, ReadinessEvidence
from .reconciliation import (
    BrokerPosition,
    BrokerReconciler,
    ReconciliationReport,
    ReconciliationStatus,
)
from .safety import (
    IndependentSafetyGate,
    SafetyBlock,
    SafetyDecision,
    SafetyState,
)


def build_research_readiness_evidence(*args, **kwargs):
    """Lazily import the research adapter to avoid execution import cycles."""
    from .research_readiness import build_research_readiness_evidence as _build
    return _build(*args, **kwargs)


__all__ = [
    "BrokerPosition",
    "BrokerReconciler",
    "IndependentSafetyGate",
    "LiveReadinessGate",
    "LiveReadinessInput",
    "LiveReadinessReport",
    "ReadinessEvidence",
    "ReconciliationReport",
    "ReconciliationStatus",
    "SafetyBlock",
    "SafetyDecision",
    "SafetyState",
    "build_research_readiness_evidence",
]
