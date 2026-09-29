"""Tests for append-only evidence-bundle persistence."""

from dataclasses import replace

import pytest

from self_learning.contracts import CandidateLifecycle
from self_learning.evidence_runner import build_evidence_bundle
from self_learning.promotion import PromotionController
from self_learning.store import DuplicateArtifactError, LearningStore
from self_learning.validation import validate_candidate
from self_learning.validation_orchestrator import ValidationRun

from tests.self_learning.test_evidence_runner import _validations


def _bundle():
    candidate = replace(
        __import__(
            "tests.self_learning.test_candidate_lifecycle",
            fromlist=["_candidate"],
        )._candidate(),
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


def test_evidence_bundle_is_persisted_as_its_own_artifact(tmp_path):
    store = LearningStore(tmp_path / "learning.jsonl")
    bundle = _bundle()

    store.add_evidence_bundle(bundle)

    assert store.count("evidence_bundle") == 1
    record = store.records("evidence_bundle")[0]
    assert record["fingerprint"] == bundle.fingerprint
    assert record["candidate_fingerprint"] == bundle.candidate_fingerprint


def test_duplicate_evidence_bundle_is_rejected(tmp_path):
    store = LearningStore(tmp_path / "learning.jsonl")
    bundle = _bundle()

    store.add_evidence_bundle(bundle)

    with pytest.raises(DuplicateArtifactError, match="already exists"):
        store.add_evidence_bundle(bundle)


def test_bundle_serialization_contains_all_stage_fingerprints(tmp_path):
    store = LearningStore(tmp_path / "learning.jsonl")
    bundle = _bundle()

    store.add_evidence_bundle(bundle)

    record = store.records("evidence_bundle")[0]
    stages = record["stages"]

    assert tuple(item["stage"] for item in stages) == (
        "BACKTEST",
        "LEAKAGE_AUDIT",
        "OOS",
        "WALK_FORWARD",
        "PAPER",
    )
    assert all(len(item["fingerprint"]) == 64 for item in stages)
