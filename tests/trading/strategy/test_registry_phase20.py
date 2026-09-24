from __future__ import annotations

import pytest

from trading.strategy.models import StrategyConfig
from trading.strategy.registry import (
    STRATEGY_APPROVED,
    STRATEGY_CANDIDATE,
    STRATEGY_RETIRED,
    StrategyRegistration,
    StrategyRegistry,
)


def _candidate(version: str = "STRAT-v2.0") -> StrategyRegistration:
    return StrategyRegistration(
        config=StrategyConfig(strategy_version=version),
        status=STRATEGY_CANDIDATE,
        validation_reference="VAL-001",
        evaluation_fingerprint="e" * 64,
        lineage_id="l" * 64,
    )


def test_candidate_registration_is_immutable_and_fingerprint_is_deterministic() -> None:
    first = _candidate()
    second = _candidate()
    assert first.config_fingerprint == second.config_fingerprint
    assert len(first.config_fingerprint) == 64


def test_constructor_rejects_direct_approved_seed() -> None:
    with pytest.raises(ValueError, match="approved strategies"):
        StrategyRegistry(
            {
                "STRAT-v2.0": StrategyRegistration(
                    config=StrategyConfig(strategy_version="STRAT-v2.0"),
                    status=STRATEGY_APPROVED,
                )
            }
        )


def test_register_is_idempotent_for_identical_strategy_identity() -> None:
    registry = StrategyRegistry()
    registration = _candidate()
    assert registry.register(registration) is registration
    assert registry.register(_candidate()) is registration


def test_register_rejects_same_version_with_different_configuration() -> None:
    registry = StrategyRegistry()
    registry.register(_candidate())
    changed = StrategyRegistration(
        config=StrategyConfig(
            strategy_version="STRAT-v2.0",
            prediction_min_probability=0.7,
        ),
        status=STRATEGY_CANDIDATE,
    )
    with pytest.raises(ValueError, match="already registered"):
        registry.register(changed)


def test_only_candidate_can_be_approved_and_provenance_is_persisted() -> None:
    registry = StrategyRegistry()
    registry.register(_candidate())

    approved = registry.approve(
        "STRAT-v2.0",
        validation_reference="VAL-001",
        evaluation_fingerprint="e" * 64,
        lineage_id="l" * 64,
        approval_reference="GOV-001",
        evaluator="human-review",
    )

    assert approved.status == STRATEGY_APPROVED
    assert approved.approval_reference == "GOV-001"
    assert approved.approval_evaluator == "human-review"
    assert approved.approval_fingerprint is not None
    assert len(approved.approval_fingerprint) == 64


def test_approval_requires_complete_provenance() -> None:
    registry = StrategyRegistry()
    registry.register(_candidate())

    with pytest.raises(ValueError, match="provenance"):
        registry.approve(
            "STRAT-v2.0",
            validation_reference="",
            evaluation_fingerprint="e" * 64,
            lineage_id="l" * 64,
            approval_reference="GOV-001",
            evaluator="human-review",
        )


def test_retirement_preserves_approval_provenance() -> None:
    registry = StrategyRegistry()
    registry.register(_candidate())
    approved = registry.approve(
        "STRAT-v2.0",
        validation_reference="VAL-001",
        evaluation_fingerprint="e" * 64,
        lineage_id="l" * 64,
        approval_reference="GOV-001",
        evaluator="human-review",
    )

    retired = registry.retire("STRAT-v2.0", reason="replaced by a later validated strategy")

    assert retired.status == STRATEGY_RETIRED
    assert retired.retirement_reason == "replaced by a later validated strategy"
    assert retired.approval_fingerprint == approved.approval_fingerprint
    assert retired.approval_reference == approved.approval_reference


def test_retired_strategy_cannot_be_approved_again() -> None:
    registry = StrategyRegistry()
    registry.register(_candidate())
    registry.retire("STRAT-v2.0", reason="test retirement")

    with pytest.raises(ValueError, match="retired strategy"):
        registry.approve(
            "STRAT-v2.0",
            validation_reference="VAL-001",
            evaluation_fingerprint="e" * 64,
            lineage_id="l" * 64,
            approval_reference="GOV-002",
            evaluator="human-review",
        )


def test_active_approved_requires_unambiguous_selection() -> None:
    registry = StrategyRegistry()
    registry.register(_candidate("STRAT-v2.0"))
    registry.register(_candidate("STRAT-v3.0"))

    registry.approve(
        "STRAT-v2.0",
        validation_reference="VAL-001",
        evaluation_fingerprint="e" * 64,
        lineage_id="l" * 64,
        approval_reference="GOV-001",
        evaluator="human-review",
    )
    registry.approve(
        "STRAT-v3.0",
        validation_reference="VAL-002",
        evaluation_fingerprint="f" * 64,
        lineage_id="m" * 64,
        approval_reference="GOV-002",
        evaluator="human-review",
    )

    with pytest.raises(ValueError, match="multiple approved"):
        registry.active_approved()
