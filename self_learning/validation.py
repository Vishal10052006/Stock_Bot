"""Controlled candidate validation and quality gates.

The module validates evidence completeness; it does not infer profitability,
promote models, or alter strategy/risk/execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .contracts import ModelCandidate, ValidationSummary


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """Required evidence stages for a promotion review."""

    required_stages: tuple[str, ...] = (
        "BACKTEST",
        "LEAKAGE_AUDIT",
        "OOS",
        "WALK_FORWARD",
        "PAPER",
    )


def validate_candidate(
    candidate: ModelCandidate,
    validations: Mapping[str, ValidationSummary],
    *,
    policy: ValidationPolicy | None = None,
) -> ValidationSummary:
    """Return a structural promotion-gate result for one candidate."""
    if not isinstance(candidate, ModelCandidate):
        raise TypeError("candidate must be a ModelCandidate")
    if not isinstance(validations, Mapping):
        raise TypeError("validations must be a mapping")

    policy = policy or ValidationPolicy()
    issues: list[str] = []
    artifacts: list[str] = []
    observations = 0

    for stage in policy.required_stages:
        result = validations.get(stage)
        if result is None:
            issues.append(f"MISSING_STAGE:{stage}")
            continue
        if not isinstance(result, ValidationSummary):
            issues.append(f"INVALID_STAGE:{stage}")
            continue

        observations += result.observations
        artifacts.extend(result.artifact_fingerprints)

        if not result.valid:
            issues.append(f"STAGE_INVALID:{stage}")
        issues.extend(f"{stage}:{issue}" for issue in result.issues)

    if candidate.evaluation_fingerprint not in artifacts:
        issues.append("CANDIDATE_EVALUATION_NOT_IN_VALIDATION_ARTIFACTS")

    if not candidate.artifact_fingerprint or candidate.artifact_fingerprint not in artifacts:
        issues.append("CANDIDATE_ARTIFACT_NOT_IN_VALIDATION_ARTIFACTS")

    for name, value in candidate.metrics.items():
        if not isfinite(float(value)):
            issues.append(f"NON_FINITE_CANDIDATE_METRIC:{name}")

    return ValidationSummary(
        stage="PROMOTION_GATE",
        valid=not issues,
        observations=observations,
        metrics=candidate.metrics,
        issues=tuple(dict.fromkeys(issues)),
        artifact_fingerprints=tuple(sorted(set(artifacts))),
        limitations=(
            "Structural validation does not infer profitability.",
            "Performance thresholds remain controlled project policy.",
        ),
    )


__all__ = ["ValidationPolicy", "validate_candidate"]
