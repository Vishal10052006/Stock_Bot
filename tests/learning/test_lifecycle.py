"""Tests for champion activation and rollback integrity."""

import pytest

from learning.lifecycle import ChampionStore
from learning.self_learning_models import ChampionRecord
from self_learning.contracts import PromotionDecision, PromotionState


def _record(model_version="model-v1", parent=None, review_fp="a" * 64):
    return ChampionRecord(
        model_version=model_version,
        status="PROMOTED",
        activated_at="2026-09-24T10:00:00+05:30",
        experiment_id="EXP-1",
        promotion_review_fingerprint=review_fp,
        parent_model_version=parent,
    )


def _decision(challenger="model-v1"):
    return PromotionDecision(
        candidate_id="C1",
        candidate_fingerprint="b" * 64,
        champion_version="model-v0",
        challenger_version=challenger,
        state=PromotionState.PROMOTED,
        reasons=("approved",),
        validation_fingerprints=("c" * 64,),
        approval_reference="approval-1",
        created_at="2026-09-24T10:00:00+05:30",
    )


def test_activation_requires_promotion_decision(tmp_path):
    with pytest.raises(ValueError, match="promotion decision is required"):
        ChampionStore(tmp_path / "champions.jsonl").activate(_record())


def test_activation_requires_promoted_decision(tmp_path):
    decision = _decision()
    blocked = PromotionDecision(
        candidate_id=decision.candidate_id,
        candidate_fingerprint=decision.candidate_fingerprint,
        champion_version=decision.champion_version,
        challenger_version=decision.challenger_version,
        state=PromotionState.BLOCKED,
        reasons=decision.reasons,
        validation_fingerprints=decision.validation_fingerprints,
    )
    with pytest.raises(ValueError, match="must be PROMOTED"):
        ChampionStore(tmp_path / "champions.jsonl").activate(
            _record(review_fp=blocked.fingerprint),
            promotion_decision=blocked,
        )


def test_activation_binds_challenger_and_review_fingerprint(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    decision = _decision("model-v1")
    store.activate(_record("model-v1", review_fp=decision.fingerprint), promotion_decision=decision)
    assert store.current() == "model-v1"

    with pytest.raises(ValueError, match="challenger"):
        store.activate(
            _record("model-v2", parent="model-v1", review_fp=decision.fingerprint),
            promotion_decision=decision,
        )


def test_activation_rejects_review_fingerprint_mismatch(tmp_path):
    decision = _decision()
    with pytest.raises(ValueError, match="fingerprint does not match"):
        ChampionStore(tmp_path / "champions.jsonl").activate(
            _record(review_fp="d" * 64),
            promotion_decision=decision,
        )


def test_successor_requires_current_parent(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    first = _decision("model-v1")
    store.activate(_record("model-v1", review_fp=first.fingerprint), promotion_decision=first)

    second = _decision("model-v2")
    with pytest.raises(ValueError, match="parent must match current"):
        store.activate(
            _record("model-v2", parent="wrong", review_fp=second.fingerprint),
            promotion_decision=second,
        )


def test_pointer_drift_is_detected(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    decision = _decision()
    store.activate(_record(review_fp=decision.fingerprint), promotion_decision=decision)
    store.pointer_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="pointer does not match history"):
        store.current()
