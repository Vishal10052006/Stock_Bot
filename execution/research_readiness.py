"""Research experiment -> readiness provenance adapter.

This module binds the exact artifacts produced by a validation execution to
the corresponding live-readiness evidence kinds. It does not mark gates true
and does not enable live execution.
"""

from __future__ import annotations

from datetime import datetime

from experiments.executor import ExperimentLineageExecution

from .readiness import ReadinessEvidence


def _artifact_fingerprint(lineage: object, key: str) -> str:
    """Return the fingerprint registered for one lineage artifact."""
    artifacts = dict(getattr(lineage, "artifact_fingerprints", ()))
    try:
        return artifacts[key]
    except KeyError as exc:
        raise ValueError(
            f"lineage is missing required research artifact: {key}"
        ) from exc


def _verify_artifact_binding(
    *,
    lineage: object,
    key: str,
    artifact: object,
) -> None:
    """Reject substitution or tampering between lineage and produced artifact."""
    expected = _artifact_fingerprint(lineage, key)
    actual = getattr(artifact, "fingerprint", None)
    if not isinstance(actual, str):
        raise TypeError(f"{key} artifact must expose a string fingerprint")
    if actual != expected:
        raise ValueError(
            f"{key} artifact fingerprint does not match experiment lineage"
        )


def build_research_readiness_evidence(
    execution: ExperimentLineageExecution,
    *,
    validated_at: datetime,
    include_backtest: bool = True,
) -> tuple[ReadinessEvidence, ...]:
    """Build lineage-bound evidence from one exact validation execution.

    Baseline/model provenance uses the experiment lineage identity. OOS,
    walk-forward, and optional backtest provenance uses the exact artifact
    fingerprints recorded in that same lineage.

    Dataset and code versions are always derived from lineage; callers cannot
    substitute independent versions for these research artifacts.
    """
    if not isinstance(execution, ExperimentLineageExecution):
        raise TypeError("execution must be an ExperimentLineageExecution")

    lineage = execution.lineage
    computed_id = lineage.computed_id()
    lineage_id = getattr(lineage, "lineage_id", "")
    if lineage_id != computed_id:
        raise ValueError("experiment lineage identity is invalid or tampered")

    _verify_artifact_binding(
        lineage=lineage,
        key="oos",
        artifact=execution.oos_report,
    )
    _verify_artifact_binding(
        lineage=lineage,
        key="walk_forward",
        artifact=execution.walk_forward_report,
    )

    evidence = [
        ReadinessEvidence.from_lineage(
            lineage,
            gate="baseline_validated",
            validated_at=validated_at,
        ),
        ReadinessEvidence.from_lineage(
            lineage,
            gate="model_validated",
            validated_at=validated_at,
        ),
        ReadinessEvidence.from_artifact(
            execution.oos_report,
            gate="oos_validated",
            evidence_kind="oos",
            dataset_version=lineage.dataset_version,
            code_version=lineage.code_version,
            validated_at=validated_at,
            source=f"lineage:{computed_id}/oos",
        ),
        ReadinessEvidence.from_artifact(
            execution.walk_forward_report,
            gate="walk_forward_validated",
            evidence_kind="walk_forward",
            dataset_version=lineage.dataset_version,
            code_version=lineage.code_version,
            validated_at=validated_at,
            source=f"lineage:{computed_id}/walk_forward",
        ),
    ]

    if include_backtest:
        if execution.backtest_result is None:
            raise ValueError(
                "include_backtest=True requires a backtest result in the execution"
            )
        _verify_artifact_binding(
            lineage=lineage,
            key="backtest",
            artifact=execution.backtest_result,
        )
        evidence.append(
            ReadinessEvidence.from_artifact(
                execution.backtest_result,
                gate="realistic_backtest_validated",
                evidence_kind="backtest",
                dataset_version=lineage.dataset_version,
                code_version=lineage.code_version,
                validated_at=validated_at,
                source=f"lineage:{computed_id}/backtest",
            )
        )

    return tuple(evidence)
