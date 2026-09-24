"""Tests for append-only self-learning persistence."""

from pathlib import Path

import pytest

from self_learning.contracts import LearningEvidence, LearningTrigger
from self_learning.store import AppendOnlyLearningStore, DuplicateArtifactError


def _evidence() -> LearningEvidence:
    return LearningEvidence(
        evidence_id="E1",
        pattern="REGIME_LOSS_CLUSTER",
        error_class="CONTEXT_LOSS_CLUSTER",
        source_trade_ids=("T1", "T2", "T3"),
        evidence_count=3,
        population_count=6,
        occurrence_rate=0.5,
        confidence=0.2,
        average_reward=-0.4,
        rationale="Repeated loss evidence in the same context.",
        trigger=LearningTrigger.ERROR_PATTERN,
    )


def test_learning_store_round_trip(tmp_path: Path) -> None:
    store = AppendOnlyLearningStore(tmp_path / "learning.jsonl")
    record = _evidence()

    store.add_evidence(record)

    assert store.count("learning_evidence") == 1
    assert store.records("learning_evidence")[0]["evidence_id"] == "E1"


def test_learning_store_rejects_duplicate_identity(tmp_path: Path) -> None:
    store = AppendOnlyLearningStore(tmp_path / "learning.jsonl")
    record = _evidence()

    store.add_evidence(record)

    with pytest.raises(DuplicateArtifactError, match="already exists"):
        store.add_evidence(record)


def test_learning_store_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "learning.jsonl"
    store = AppendOnlyLearningStore(path)
    store.add_evidence(_evidence())

    before = path.read_text(encoding="utf-8")
    store.add_evidence(
        LearningEvidence(
            evidence_id="E2",
            pattern="HIGH_CONFIDENCE_FALSE_SIGNAL",
            error_class="HIGH_CONFIDENCE_FAILURE",
            source_trade_ids=("T4", "T5", "T6"),
            evidence_count=3,
            population_count=7,
            occurrence_rate=3 / 7,
            confidence=0.15,
            average_reward=-0.3,
            rationale="Repeated false-positive evidence.",
        )
    )
    after = path.read_text(encoding="utf-8")

    assert after.startswith(before)
    assert after.count("\n") == 2
