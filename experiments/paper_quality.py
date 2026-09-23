"""Aggregate structural quality reporting for persisted paper evidence.

This module reports coverage and validation state across journal records. It
does not rank runs, infer profitability, or authorize live execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from .paper_evidence import validate_paper_evidence
from .paper_journal import PaperEvidenceRecord


@dataclass(frozen=True, slots=True)
class PaperEvidenceQualityReport:
    """Immutable structural quality report across paper-evidence records."""

    record_count: int
    valid_record_count: int
    invalid_record_count: int
    total_signals: int
    total_fills: int
    total_slippage_observations: int
    total_latency_observations: int
    total_false_signals: int
    total_drawdown_observations: int
    total_regime_observations: int
    total_calibration_observations: int
    total_operational_events: int
    total_operational_errors: int
    total_stale_events: int
    dataset_versions: tuple[str, ...]
    code_versions: tuple[str, ...]
    evidence_versions: tuple[str, ...]
    issues: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        payload = {
            "record_count": self.record_count,
            "valid_record_count": self.valid_record_count,
            "invalid_record_count": self.invalid_record_count,
            "totals": {
                "signals": self.total_signals,
                "fills": self.total_fills,
                "slippage": self.total_slippage_observations,
                "latency": self.total_latency_observations,
                "false_signals": self.total_false_signals,
                "drawdown": self.total_drawdown_observations,
                "regime": self.total_regime_observations,
                "calibration": self.total_calibration_observations,
                "operational_events": self.total_operational_events,
                "operational_errors": self.total_operational_errors,
                "stale_events": self.total_stale_events,
            },
            "dataset_versions": self.dataset_versions,
            "code_versions": self.code_versions,
            "evidence_versions": self.evidence_versions,
            "issues": self.issues,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def valid(self) -> bool:
        """Return whether every supplied record passed structural validation."""
        return self.record_count > 0 and self.invalid_record_count == 0 and not self.issues


def assess_paper_evidence(
    records: Iterable[PaperEvidenceRecord],
) -> PaperEvidenceQualityReport:
    """Aggregate journal records without evaluating trading performance."""
    materialized = tuple(records)
    for record in materialized:
        if not isinstance(record, PaperEvidenceRecord):
            raise TypeError("records must contain PaperEvidenceRecord objects")

    issues: list[str] = []
    valid_count = 0
    totals = {
        "total_signals": 0,
        "total_fills": 0,
        "total_slippage_observations": 0,
        "total_latency_observations": 0,
        "total_false_signals": 0,
        "total_drawdown_observations": 0,
        "total_regime_observations": 0,
        "total_calibration_observations": 0,
        "total_operational_events": 0,
        "total_operational_errors": 0,
        "total_stale_events": 0,
    }

    dataset_versions: set[str] = set()
    code_versions: set[str] = set()
    evidence_versions: set[str] = set()

    field_map = {
        "total_signals": "signal_count",
        "total_fills": "fill_count",
        "total_slippage_observations": "slippage_observation_count",
        "total_latency_observations": "latency_observation_count",
        "total_false_signals": "false_signal_count",
        "total_drawdown_observations": "drawdown_observation_count",
        "total_regime_observations": "regime_observation_count",
        "total_calibration_observations": "calibration_observation_count",
        "total_operational_events": "operational_event_count",
        "total_operational_errors": "operational_error_count",
        "total_stale_events": "stale_event_count",
    }

    for record in materialized:
        evidence = record.evidence
        report = validate_paper_evidence(evidence)
        if report.valid:
            valid_count += 1
        else:
            issues.extend(f"{record.run_id}: {issue}" for issue in report.issues)

        dataset_versions.add(evidence.dataset_version)
        code_versions.add(evidence.code_version)
        evidence_versions.add(evidence.evidence_version)

        for total_name, source_name in field_map.items():
            totals[total_name] += getattr(evidence, source_name)

    return PaperEvidenceQualityReport(
        record_count=len(materialized),
        valid_record_count=valid_count,
        invalid_record_count=len(materialized) - valid_count,
        **totals,
        dataset_versions=tuple(sorted(dataset_versions)),
        code_versions=tuple(sorted(code_versions)),
        evidence_versions=tuple(sorted(evidence_versions)),
        issues=tuple(issues),
    )
