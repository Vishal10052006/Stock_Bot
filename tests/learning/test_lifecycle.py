"""Tests for champion activation and rollback pointer integrity."""

import json

import pytest

from learning.lifecycle import ChampionStore
from learning.self_learning_models import ChampionRecord


def _record(model_version="model-v1", parent=None):
    return ChampionRecord(
        model_version=model_version,
        status="PROMOTED",
        activated_at="2026-09-24T10:00:00+05:30",
        experiment_id="EXP-1",
        promotion_review_fingerprint="a" * 64,
        parent_model_version=parent,
    )


def test_activation_requires_promoted_record(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    record = _record()
    record = ChampionRecord(
        model_version=record.model_version,
        status="ELIGIBLE",
        activated_at=record.activated_at,
        experiment_id=record.experiment_id,
        promotion_review_fingerprint=record.promotion_review_fingerprint,
    )
    with pytest.raises(ValueError, match="PROMOTED"):
        store.activate(record)


def test_activation_and_pointer_are_bound_to_history(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    store.activate(_record())
    assert store.current() == "model-v1"

    store.activate(_record("model-v2", parent="model-v1"))
    assert store.current() == "model-v2"
    assert len(store.history()) == 2


def test_activation_rejects_existing_pointer_drift(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    store.activate(_record())
    store.pointer_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="pointer does not match history"):
        store.current()

    with pytest.raises(ValueError, match="pointer does not match history"):
        store.activate(_record("model-v2", parent="model-v1"))


def test_activation_requires_current_parent(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    store.activate(_record())
    with pytest.raises(ValueError, match="parent must match current"):
        store.activate(_record("model-v2", parent="wrong"))


def test_rollback_updates_history_and_pointer(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    store.activate(_record())
    store.activate(_record("model-v2", parent="model-v1"))

    rolled = store.rollback(
        reason="validated degradation",
        updated_at="2026-09-24T11:00:00+05:30",
    )
    assert rolled.champion_version == "model-v1"
    assert rolled.previous_verified_version == "model-v2"
    assert store.current() == "model-v1"


def test_pointer_without_history_is_rejected(tmp_path):
    path = tmp_path / "champions.jsonl"
    store = ChampionStore(path)
    store.pointer_path.write_text("model-v1", encoding="utf-8")

    with pytest.raises(ValueError, match="pointer exists without history"):
        store.current()
