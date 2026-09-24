"""Tests for the persistent experiment and champion registries."""

from pathlib import Path

import pytest

from experiments.definition import ExperimentDefinition
from experiments.record import ExperimentRecord
from self_learning.champion import ChampionState, ChampionStateStore
from self_learning.experiments import ExperimentRegistry


def _definition(experiment_id: str = "EXP-1") -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id=experiment_id,
        research_question="Does the candidate improve robustness?",
        hypothesis="Candidate improves OOS quality.",
        failure_criterion="Reject on OOS/walk-forward deterioration.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        period_start="2025-01-01",
        period_end="2026-01-01",
        symbols=("ITC",),
        method="temporal-oos-walk-forward",
        allowed_change=("baseline.minimum_rvol",),
    )


def test_experiment_registry_round_trip(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "experiments.jsonl")
    definition = _definition()
    record = ExperimentRecord.from_definition(
        definition,
        observations=10,
        decision="INCONCLUSIVE",
    )

    artifact = registry.register(definition, record)

    assert registry.records() == (artifact,)
    assert artifact.definition.experiment_id == "EXP-1"


def test_experiment_registry_rejects_duplicate_definition(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "experiments.jsonl")
    definition = _definition()
    record = ExperimentRecord.from_definition(definition, observations=10)

    registry.register(definition, record)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition, record)


def test_experiment_registry_rejects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "experiments.jsonl"
    registry = ExperimentRegistry(path)
    definition = _definition()
    record = ExperimentRecord.from_definition(definition, observations=10)
    registry.register(definition, record)

    payload = path.read_text(encoding="utf-8").replace(
        '"observations":10',
        '"observations":11',
    )
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint"):
        registry.records()


def test_champion_state_store_round_trip_and_rollback(tmp_path: Path) -> None:
    store = ChampionStateStore(tmp_path / "champion.jsonl")
    first = ChampionState(
        champion_version="model-v1",
        previous_verified_version=None,
        updated_at="2026-09-24T10:00:00+05:30",
    )
    store.append(first)

    second = ChampionState(
        champion_version="model-v2",
        previous_verified_version="model-v1",
        promotion_fingerprint="a" * 64,
        updated_at="2026-09-24T11:00:00+05:30",
    )
    store.append(second)

    assert store.current == second

    rolled_back = store.rollback(
        reason="controlled degradation",
        updated_at="2026-09-24T12:00:00+05:30",
    )

    assert rolled_back.champion_version == "model-v1"
    assert rolled_back.previous_verified_version == "model-v2"
    assert store.current == rolled_back
