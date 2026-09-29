"""Integration tests for the immutable evidence-bundle ledger boundary."""

from dataclasses import replace

import pytest

from self_learning.contracts import CandidateLifecycle
from self_learning.evidence_runner import (
    REQUIRED_STAGES,
    build_evidence_bundle,
)
from self_learning.promotion import PromotionController
from self_learning.store import DuplicateArtifactError, LearningStore
from self_learning.validation import validate_candidate
from self_learning.validation_orchestrator import ValidationRun

from tests.self_learning.test_candidate_lifecycle import _candidate
from tests.self_learning.test_evidence_runner import _validations


def _ready_bundle():
    candidate = replace(
        _candidate(),
        lifecycle=CandidateLifecycle.PROMOTION_REVIEW,
    )
    validations = _validations(candidate)
    run = ValidationRun(
        candidate_fingerprint=candidate.fingerprint,
        stages=tuple(validations.values()),
        gate=validate_candidate(candidate, validations),
    )
    review = PromotionController().review_run(
        champion_version="model-v1",
        challenger=candidate,
        validation_run=run,
    )
    return build_evidence_bundle(candidate, run, review)


def test_bundle_round_trips_through_learning_ledger(tmp_path):
    store = LearningStore(tmp_path / "learning.jsonl")
    bundle = _ready_bundle()

    store.add_evidence_bundle(bundle)

    assert store.count("evidence_bundle") == 1
    record = store.records("evidence_bundle")[0]
    assert record["fingerprint"] == bundle.fingerprint
    assert record["candidate_fingerprint"] == bundle.candidate_fingerprint
    assert tuple(stage["stage"] for stage in record["stages"]) == REQUIRED_STAGES


def test_duplicate_bundle_is_rejected(tmp_path):
    store = LearningStore(tmp_path / "learning.jsonl")
    bundle = _ready_bundle()

    store.add_evidence_bundle(bundle)

    with pytest.raises(DuplicateArtifactError, match="already exists"):
        store.add_evidence_bundle(bundle)


def test_store_rejects_non_bundle_objects(tmp_path):
    store = LearningStore(tmp_path / "learning.jsonl")

    class Fake:
        fingerprint = "a" * 64

    with pytest.raises(TypeError, match="fingerprint and to_dict"):
        store.add_evidence_bundle(Fake())
