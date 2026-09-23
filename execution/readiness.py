"""Live-readiness gate for the frozen trading specification.

This module only evaluates whether explicitly supplied gates are satisfied.
It never enables live execution and never contacts a broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.paper_quality import PaperEvidenceQualityReport


@dataclass(frozen=True, slots=True)
class LiveReadinessInput:
    historical_data_validated: bool
    indicators_validated: bool
    features_leakage_safe: bool
    labels_validated: bool
    baseline_validated: bool
    model_validated: bool
    realistic_backtest_validated: bool
    leakage_audit_passed: bool
    oos_validated: bool
    walk_forward_validated: bool
    paper_evidence_validated: bool
    risk_controls_validated: bool
    monitoring_validated: bool
    kill_switch_validated: bool
    broker_integration_validated: bool
    reconciliation_validated: bool
    compliance_verified_current: bool


@dataclass(frozen=True, slots=True)
class LiveReadinessReport:
    ready: bool
    failed_gates: tuple[str, ...]


class LiveReadinessGate:
    """Fail-closed checklist corresponding to TRADING_SPECIFICATION §26."""

    _FIELDS = (
        "historical_data_validated",
        "indicators_validated",
        "features_leakage_safe",
        "labels_validated",
        "baseline_validated",
        "model_validated",
        "realistic_backtest_validated",
        "leakage_audit_passed",
        "oos_validated",
        "walk_forward_validated",
        "paper_evidence_validated",
        "risk_controls_validated",
        "monitoring_validated",
        "kill_switch_validated",
        "broker_integration_validated",
        "reconciliation_validated",
        "compliance_verified_current",
    )

    def evaluate(
        self,
        gates: LiveReadinessInput,
        *,
        paper_evidence_quality: PaperEvidenceQualityReport | None = None,
    ) -> LiveReadinessReport:
        if not isinstance(gates, LiveReadinessInput):
            raise TypeError("gates must be a LiveReadinessInput")

        failed = [
            field
            for field in self._FIELDS
            if not getattr(gates, field)
        ]
        if paper_evidence_quality is not None:
            valid = getattr(paper_evidence_quality, "valid", None)
            if not isinstance(valid, bool):
                raise TypeError(
                    "paper_evidence_quality must expose a boolean valid property"
                )
            if not valid:
                failed.append("paper_evidence_quality_validated")
        failed = tuple(failed)
        return LiveReadinessReport(
            ready=not failed,
            failed_gates=failed,
        )
