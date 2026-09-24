"""Phase-20 model registry tests."""

from __future__ import annotations

import pytest

from ml.model_registry import (
    ModelApproval,
    ModelRegistry,
    ModelRegistryRecord,
    ModelRegistryStatus,
)


def _record(**overrides: object) -> ModelRegistryRecord:
    """Build deterministic registry metadata for unit tests."""
    values = {
        "model_version": "signal-v2.0",
        "model_family": "logistic_regression",
        "feature_version": "features-v5",
        "dataset_version": "dataset-v1",
        "code_version": "code-v2",
        "training_period_start": "2024-01-01",
        "training_period_end": "2025-01-01",
        "validation_period_start": "2025-01-02",
        "validation_period_end": "2025-04-01",
        "test_period_start": "2025-04-02",
        "test_period_end": "2025-07-01",
        "hyperparameters": {"C": 1.0, "class_weight": "balanced"},
        "metrics": {"balanced_accuracy": 0.61, "log_loss": 0.92},
        "approval_status": ModelRegistryStatus.CANDIDATE.value,
        "artifact_uri": "artifacts/models/signal-v2.0.joblib",
        "artifact_fingerprint": "a" * 64,
        "strategy_version": "STRAT-v2.0",
        "lineage_id": "b" * 64,
        "evaluation_fingerprint": "c" * 64,
    }
    values.update(overrides)
    return ModelRegistryRecord(**values)


def test_record_fingerprint_is_deterministic() -> None:
    first = _record()
    second = _record()

    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64


def test_registry_is_append_only_per_model_version() -> None:
    registry = ModelRegistry()
    first = registry.register(_record())

    assert registry.get("signal-v2.0") is first

    with pytest.raises(ValueError, match="different metadata"):
        registry.register(_record(metrics={"balanced_accuracy": 0.70}))


def test_registry_allows_idempotent_re_registration_of_same_record() -> None:
    registry = ModelRegistry()
    first = registry.register(_record())
    second = registry.register(_record())

    assert first is second
    assert registry.versions() == ("signal-v2.0",)


def test_direct_approved_registration_is_forbidden() -> None:
    registry = ModelRegistry()

    with pytest.raises(ValueError, match="through approve"):
        registry.register(
            _record(
                approval_status=ModelRegistryStatus.APPROVED.value,
                approval_reference="approval-1",
            )
        )


def test_candidate_requires_artifact_identity_for_approval() -> None:
    registry = ModelRegistry()
    registry.register(_record(artifact_fingerprint=""))

    approval = ModelApproval(
        model_fingerprint=registry.get("signal-v2.0").fingerprint,
        approval_reference="approval-1",
        evaluator="controlled-review",
        approved_at="2026-09-24T16:00:00+05:30",
    )

    with pytest.raises(ValueError, match="artifact_fingerprint"):
        registry.approve("signal-v2.0", approval)


def test_approval_requires_exact_registered_model_identity() -> None:
    registry = ModelRegistry()
    registry.register(_record())

    approval = ModelApproval(
        model_fingerprint="d" * 64,
        approval_reference="approval-1",
        evaluator="controlled-review",
        approved_at="2026-09-24T16:00:00+05:30",
    )

    with pytest.raises(ValueError, match="does not match"):
        registry.approve("signal-v2.0", approval)


def test_approval_is_explicit_and_preserves_artifact_lineage() -> None:
    registry = ModelRegistry()
    candidate = registry.register(_record())

    approval = ModelApproval(
        model_fingerprint=candidate.fingerprint,
        approval_reference="approval-2026-09-24-001",
        evaluator="controlled-review",
        approved_at="2026-09-24T16:00:00+05:30",
    )

    approved = registry.approve("signal-v2.0", approval)

    assert approved.approval_status == ModelRegistryStatus.APPROVED.value
    assert approved.artifact_fingerprint == "a" * 64
    assert approved.lineage_id == "b" * 64
    assert approved.evaluation_fingerprint == "c" * 64
    assert approved.approval_reference == "approval-2026-09-24-001"
    assert approved.approval_evaluator == "controlled-review"
    assert approved.approval_timestamp == "2026-09-24T16:00:00+05:30"
    assert approved.approval_fingerprint == approval.fingerprint
    assert approved.fingerprint != candidate.fingerprint


def test_retirement_preserves_historical_version() -> None:
    registry = ModelRegistry()
    registry.register(_record())

    retired = registry.retire("signal-v2.0", reason="superseded by controlled review")

    assert retired.approval_status == ModelRegistryStatus.RETIRED.value
    assert registry.get("signal-v2.0").fingerprint == retired.fingerprint
    assert registry.versions() == ("signal-v2.0",)


def test_retired_model_cannot_be_approved() -> None:
    registry = ModelRegistry()
    registry.register(_record())
    registry.retire("signal-v2.0", reason="test retirement")

    approval = ModelApproval(
        model_fingerprint=registry.get("signal-v2.0").fingerprint,
        approval_reference="approval-2",
        evaluator="controlled-review",
        approved_at="2026-09-24T16:00:00+05:30",
    )

    with pytest.raises(ValueError, match="retired"):
        registry.approve("signal-v2.0", approval)


def test_status_queries_are_deterministic() -> None:
    registry = ModelRegistry()
    registry.register(_record(model_version="signal-v1.0"))
    registry.register(_record(model_version="signal-v2.0"))

    candidates = registry.by_status(ModelRegistryStatus.CANDIDATE)

    assert tuple(item.model_version for item in candidates) == (
        "signal-v1.0",
        "signal-v2.0",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_fingerprint", "not-a-sha"),
        ("lineage_id", "not-a-sha"),
        ("evaluation_fingerprint", "not-a-sha"),
    ],
)
def test_registry_rejects_malformed_artifact_identities(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        _record(**{field: value})


def test_approved_record_requires_governance_evidence() -> None:
    with pytest.raises(ValueError, match="approval_reference"):
        _record(approval_status=ModelRegistryStatus.APPROVED.value)


def test_registry_preserves_state_history_across_approval() -> None:
    registry = ModelRegistry()
    candidate = registry.register(_record())

    approval = ModelApproval(
        model_fingerprint=candidate.fingerprint,
        approval_reference="approval-history",
        evaluator="controlled-review",
        approved_at="2026-09-24T16:00:00+05:30",
    )
    approved = registry.approve("signal-v2.0", approval)

    history = registry.history("signal-v2.0")

    assert history == (candidate, approved)
    assert history[0].fingerprint == candidate.fingerprint
    assert history[1].fingerprint == approved.fingerprint


def test_registry_metadata_is_immutable() -> None:
    hyperparameters = {"nested": {"value": 1}}
    record = _record(hyperparameters=hyperparameters)

    hyperparameters["nested"]["value"] = 99

    assert record.hyperparameters["nested"]["value"] == 1

    with pytest.raises(TypeError):
        record.hyperparameters["new"] = 1  # type: ignore[index]


def test_registry_constructor_rejects_approved_seed_state() -> None:
    approved = _record(
        approval_status=ModelRegistryStatus.APPROVED.value,
        approval_reference="approval-seed",
        approval_fingerprint="d" * 64,
        approval_evaluator="controlled-review",
        approval_timestamp="2026-09-24T16:00:00+05:30",
    )

    with pytest.raises(ValueError, match="through approve"):
        ModelRegistry({approved.model_version: approved})


def test_registry_constructor_rejects_mismatched_version_key() -> None:
    record = _record(model_version="signal-v2.0")

    with pytest.raises(ValueError, match="key must match"):
        ModelRegistry({"wrong-key": record})


def test_registry_rejects_non_finite_metrics() -> None:
    with pytest.raises(ValueError, match="finite"):
        _record(metrics={"balanced_accuracy": float("nan")})

    with pytest.raises(ValueError, match="finite"):
        _record(metrics={"balanced_accuracy": float("inf")})


def test_registry_requires_candidate_status_for_approval() -> None:
    registry = ModelRegistry()
    registry.register(_record(approval_status=ModelRegistryStatus.RESEARCH_ONLY.value))

    approval = ModelApproval(
        model_fingerprint=registry.get("signal-v2.0").fingerprint,
        approval_reference="approval-research",
        evaluator="controlled-review",
        approved_at="2026-09-24T16:00:00+05:30",
    )

    with pytest.raises(ValueError, match="only CANDIDATE"):
        registry.approve("signal-v2.0", approval)


def test_retirement_persists_reason_and_preserves_approval_provenance() -> None:
    registry = ModelRegistry()
    candidate = registry.register(_record())

    approval = ModelApproval(
        model_fingerprint=candidate.fingerprint,
        approval_reference="approval-retire",
        evaluator="controlled-review",
        approved_at="2026-09-24T16:00:00+05:30",
    )
    approved = registry.approve("signal-v2.0", approval)
    retired = registry.retire(
        "signal-v2.0",
        reason="superseded after controlled evaluation",
    )

    assert retired.retirement_reason == "superseded after controlled evaluation"
    assert retired.approval_fingerprint == approved.approval_fingerprint
    assert retired.approval_evaluator == approved.approval_evaluator
    assert retired.approval_timestamp == approved.approval_timestamp
    assert registry.history("signal-v2.0") == (candidate, approved, retired)
