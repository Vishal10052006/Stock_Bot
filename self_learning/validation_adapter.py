"""Unified validation adapter for existing research boundaries.

The adapter consumes existing OOS/leakage/paper artifacts and converts them
into the Self-Learning Engine's neutral ValidationSummary contracts.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from backtesting.leakage_audit import LeakageAuditReport, audit_training_dataset
from .contracts import ValidationSummary


def validate_dataset_boundary(
    data: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    label_column: str = "label",
) -> ValidationSummary:
    """Run the existing Phase-13 dataset leakage audit."""
    report: LeakageAuditReport = audit_training_dataset(
        data,
        feature_columns=feature_columns,
        label_column=label_column,
    )
    return ValidationSummary(
        stage="LEAKAGE_AUDIT",
        valid=report.passed,
        observations=len(data),
        metrics={"checks_passed": float(sum(check.passed for check in report.checks))},
        issues=tuple(report.failed_checks),
        limitations=(),
        artifact_fingerprints=(),
    )


def summarize_artifact(
    stage: str,
    artifact: Any,
    *,
    observations: int,
    metrics: Mapping[str, float] | None = None,
    valid: bool = True,
    issues: tuple[str, ...] = (),
) -> ValidationSummary:
    """Wrap an existing immutable artifact without changing its semantics."""
    fingerprint = getattr(artifact, "fingerprint", None)
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise ValueError(f"{stage} artifact must expose a SHA-256 fingerprint")
    return ValidationSummary(
        stage=stage,
        valid=valid,
        observations=observations,
        metrics=metrics or {},
        limitations=(),
        issues=issues,
        artifact_fingerprints=(fingerprint,),
    )
