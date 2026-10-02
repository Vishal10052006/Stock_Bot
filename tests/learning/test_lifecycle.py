"""Tests for champion activation, promotion binding, and rollback integrity."""

import json

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


def test_activation_and_pointer_are_bound_to_history(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    decision = _decision("model-v1")
    store.activate(
        _record("model-v1", review_fp=decision.fingerprint),
        promotion_decision=decision,
    )
    assert store.current() == "model-v1"

    second = _decision("model-v2")
    store.activate(
        _record("model-v2", parent="model-v1", review_fp=second.fingerprint),
        promotion_decision=second,
    )
    assert store.current() == "model-v2"
    assert len(store.history()) == 2


def test_activation_rejects_existing_pointer_drift(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    decision = _decision()
    store.activate(_record(review_fp=decision.fingerprint), promotion_decision=decision)
    store.pointer_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="pointer does not match history"):
        store.current()

    with pytest.raises(ValueError, match="pointer does not match history"):
        store.activate(
            _record("model-v2", parent="model-v1", review_fp=_decision("model-v2").fingerprint),
            promotion_decision=_decision("model-v2"),
        )


def test_activation_rejects_naive_activation_timestamp(tmp_path):
    decision = _decision()
    naive = ChampionRecord(
        model_version="model-v1",
        status="PROMOTED",
        activated_at="2026-09-24T10:00:00",
        experiment_id="EXP-1",
        promotion_review_fingerprint=decision.fingerprint,
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        ChampionStore(tmp_path / "champions.jsonl").activate(
            naive,
            promotion_decision=decision,
        )


def test_activation_binds_challenger_and_review_fingerprint(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    decision = _decision("model-v1")
    store.activate(_record("model-v1", review_fp=decision.fingerprint), promotion_decision=decision)

    mismatched_decision = _decision("model-v1")
    with pytest.raises(
        ValueError,
        match="fingerprint does not match champion record",
    ):
        store.activate(
            _record(
                "model-v2",
                parent="model-v1",
                review_fp=mismatched_decision.fingerprint,
            ),
            promotion_decision=_decision("model-v2"),
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


def test_rollback_updates_history_and_pointer(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    first = _decision("model-v1")
    store.activate(_record("model-v1", review_fp=first.fingerprint), promotion_decision=first)
    second = _decision("model-v2")
    store.activate(
        _record("model-v2", parent="model-v1", review_fp=second.fingerprint),
        promotion_decision=second,
    )

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


def test_pointer_drift_is_detected(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    decision = _decision()
    store.activate(_record(review_fp=decision.fingerprint), promotion_decision=decision)
    store.pointer_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="pointer does not match history"):
        store.current()


def test_history_requires_fingerprint(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    decision = _decision()
    store.activate(_record(review_fp=decision.fingerprint), promotion_decision=decision)
    line = store.history_path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    payload.pop("fingerprint")
    store.history_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint is required"):
        store.history()


def test_history_rejects_tampered_parent_chain(tmp_path):
    store = ChampionStore(tmp_path / "champions.jsonl")
    first = _decision("model-v1")
    store.activate(
        _record("model-v1", review_fp=first.fingerprint),
        promotion_decision=first,
    )
    second = _decision("model-v2")
    store.activate(
        _record("model-v2", parent="model-v1", review_fp=second.fingerprint),
        promotion_decision=second,
    )

    lines = store.history_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[1])
    payload["parent_model_version"] = "tampered-parent"
    forged = ChampionRecord(
        model_version=payload["model_version"],
        status=payload["status"],
        activated_at=payload["activated_at"],
        experiment_id=payload["experiment_id"],
        promotion_review_fingerprint=payload["promotion_review_fingerprint"],
        parent_model_version=payload["parent_model_version"],
        rollback_of=payload["rollback_of"],
    )
    payload["fingerprint"] = forged.fingerprint
    lines[1] = json.dumps(payload)
    store.history_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="parent mismatch"):
        store.history()
