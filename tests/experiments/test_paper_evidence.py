from experiments.paper_evidence import (
    PaperEvidenceSnapshot,
    validate_paper_evidence,
)


def _valid_snapshot() -> PaperEvidenceSnapshot:
    return PaperEvidenceSnapshot(
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-2026-09",
        code_version="abc123",
        signal_count=20,
        fill_count=18,
        slippage_observation_count=18,
        latency_observation_count=18,
        false_signal_count=5,
        drawdown_observation_count=18,
        regime_observation_count=18,
        calibration_observation_count=18,
        operational_event_count=18,
        operational_error_count=1,
        stale_event_count=1,
    )


def test_paper_evidence_accepts_complete_consistent_snapshot() -> None:
    report = validate_paper_evidence(_valid_snapshot())

    assert report.valid
    assert not report.issues
    assert len(report.evidence_fingerprint) == 64


def test_paper_evidence_rejects_missing_observations() -> None:
    snapshot = _valid_snapshot()
    snapshot = PaperEvidenceSnapshot(
        **{
            **{
                field: getattr(snapshot, field)
                for field in snapshot.__dataclass_fields__
            },
            "latency_observation_count": 0,
        }
    )

    report = validate_paper_evidence(snapshot)

    assert not report.valid
    assert "latency_observation_count" in " ".join(report.issues)


def test_paper_evidence_rejects_inconsistent_counts() -> None:
    snapshot = _valid_snapshot()
    snapshot = PaperEvidenceSnapshot(
        **{
            **{
                field: getattr(snapshot, field)
                for field in snapshot.__dataclass_fields__
            },
            "fill_count": 21,
        }
    )

    report = validate_paper_evidence(snapshot)

    assert not report.valid
    assert "fill_count cannot exceed signal_count" in report.issues
