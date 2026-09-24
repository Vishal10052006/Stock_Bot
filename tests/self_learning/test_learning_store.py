"""Tests for a production-safe, append-only learning ledger.

The ledger is a research memory. It must not become a broker/execution state
store, and duplicate identities must be rejected.
"""

from pathlib import Path

import pytest

from self_learning.contracts import LearningEvidence, LearningTrigger
from self_learning.store import AppendOnlyLearningStore, DuplicateArtifactError


def _evidence(evidence_id: str) -> LearningEvidence:
    return LearningEvidence(
        evidence_id=evidence_id,
        pattern="REGIME_LOSS_CLUSTER",
        error_class="CONTEXT_LOSS_CLUSTER",
        source_trade_ids=(f"{evidence_id}-T1", f"{evidence_id}-T2", f"{evidence_id}-T3"),
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
    record = _evidence("E1")

    store.add_evidence(record)

    assert store.count("learning_evidence") == 1
    assert store.records("learning_evidence")[0]["evidence_id"] == "E1"


def test_learning_store_rejects_duplicate_identity(tmp_path: Path) -> None:
    store = AppendOnlyLearningStore(tmp_path / "learning.jsonl")
    record = _evidence("E1")

    store.add_evidence(record)

    with pytest.raises(DuplicateArtifactError, match="already exists"):
        store.add_evidence(record)


def test_learning_store_preserves_existing_lines(tmp_path: Path) -> None:
    path = tmp_path / "learning.jsonl"
    store = AppendOnlyLearningStore(path)
    store.add_evidence(_evidence("E1"))

    before = path.read_text(encoding="utf-8")
    store.add_evidence(_evidence("E2"))
    after = path.read_text(encoding="utf-8")

    assert after.startswith(before)
    assert after.count("\n") == 2
