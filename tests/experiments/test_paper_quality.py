from experiments.paper_evidence import PaperEvidenceSnapshot
from experiments.paper_journal import PaperEvidenceRecord
from experiments.paper_quality import assess_paper_evidence


def _record(*, valid: bool) -> PaperEvidenceRecord:
    snapshot = PaperEvidenceSnapshot(
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-v1",
        code_version="code-v1",
        signal_count=10,
        fill_count=8,
        slippage_observation_count=8,
        latency_observation_count=8,
        false_signal_count=1,
        drawdown_observation_count=8,
        regime_observation_count=8,
        calibration_observation_count=8,
        operational_event_count=8,
        operational_error_count=1,
        stale_event_count=0,
    )
    if not valid:
        snapshot = PaperEvidenceSnapshot(
            evidence_version="PAPER-EVIDENCE-v1",
            dataset_version="paper-v1",
            code_version="code-v1",
            signal_count=10,
            fill_count=8,
            slippage_observation_count=8,
            latency_observation_count=8,
            false_signal_count=1,
            drawdown_observation_count=0,
            regime_observation_count=8,
            calibration_observation_count=8,
            operational_event_count=8,
            operational_error_count=1,
            stale_event_count=0,
        )
    return PaperEvidenceRecord.create(
        evidence=snapshot,
        period_start="2026-09-21T09:15:00+00:00",
        period_end="2026-09-21T15:30:00+00:00",
        source_run_id="paper-run-valid" if valid else "paper-run-invalid",
    )


def test_quality_report_aggregates_counts_and_versions() -> None:
    report = assess_paper_evidence((_record(valid=True),))

    assert report.valid
    assert report.record_count == 1
    assert report.valid_record_count == 1
    assert report.total_signals == 10
    assert report.total_fills == 8
    assert report.dataset_versions == ("paper-v1",)


def test_quality_report_surfaces_structural_invalidity_without_ranking() -> None:
    report = assess_paper_evidence((_record(valid=False),))

    assert not report.valid
    assert report.invalid_record_count == 1
    assert any("drawdown_observation_count" in issue for issue in report.issues)


def test_quality_report_requires_at_least_one_record() -> None:
    report = assess_paper_evidence(())

    assert not report.valid
    assert report.record_count == 0
