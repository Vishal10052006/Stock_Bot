from pathlib import Path

import pandas as pd
import pytest

from experiments.paper_evidence import PaperEvidenceSnapshot
from experiments.paper_journal import PaperEvidenceJournal, PaperEvidenceRecord


def _snapshot() -> PaperEvidenceSnapshot:
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


def _complete_step(timestamp: str) -> SimpleNamespace:
    strategy = SimpleNamespace(
        direction=StrategyDirection.LONG,
        regime="TREND_UP",
        timestamp=pd.Timestamp(timestamp, tz="UTC"),
        prediction_probability=0.8,
    )
    order = SimpleNamespace(status=PaperOrderStatus.FILLED)
    return SimpleNamespace(strategy=strategy, order=order)


def _record(source_run_id: str = "paper-run-001") -> PaperEvidenceRecord:
    return PaperEvidenceRecord.create(
        evidence=_snapshot(),
        period_start=pd.Timestamp("2026-09-01 09:15:00", tz="UTC"),
        period_end=pd.Timestamp("2026-09-23 15:30:00", tz="UTC"),
        source_run_id=source_run_id,
    )


def test_record_run_id_is_deterministic() -> None:
    first = _record()
    second = _record()

    assert first.run_id == second.run_id
    assert first.fingerprint == second.fingerprint


def test_record_identity_changes_when_source_run_changes() -> None:
    first = _record("paper-run-001")
    second = _record("paper-run-002")

    assert first.run_id != second.run_id


def test_journal_appends_and_reloads(tmp_path: Path) -> None:
    journal = PaperEvidenceJournal(tmp_path / "paper_evidence.jsonl")
    record = _record()

    journal.append(record)

    assert journal.records() == (record,)


def test_journal_rejects_duplicate_run(tmp_path: Path) -> None:
    journal = PaperEvidenceJournal(tmp_path / "paper_evidence.jsonl")
    record = _record()
    journal.append(record)

    with pytest.raises(ValueError, match="already exists"):
        journal.append(record)


def test_journal_rejects_tampered_run_identity(tmp_path: Path) -> None:
    journal_path = tmp_path / "paper_evidence.jsonl"
    journal = PaperEvidenceJournal(journal_path)
    journal.append(_record())

    payload = journal_path.read_text(encoding="utf-8")
    journal_path.write_text(
        payload.replace('"source_run_id":"paper-run-001"', '"source_run_id":"tampered"'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="run_id"):
        journal.records()


def test_record_requires_timezone_aware_period() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PaperEvidenceRecord.create(
            evidence=_snapshot(),
            period_start="2026-09-01 09:15:00",
            period_end="2026-09-23 15:30:00+00:00",
            source_run_id="paper-run-001",
        )


def test_persist_paper_decision_run_connects_collection_to_journal(tmp_path: Path) -> None:
    run = SimpleNamespace(
        steps=(
            _complete_step("2026-09-23 09:15:00"),
            _complete_step("2026-09-23 09:20:00"),
        )
    )
    journal = PaperEvidenceJournal(tmp_path / "paper_evidence.jsonl")

    record = persist_paper_decision_run(
        run,
        journal=journal,
        source_run_id="paper-run-001",
        fill_timestamps={
            0: pd.Timestamp("2026-09-23 09:15:01", tz="UTC"),
            1: pd.Timestamp("2026-09-23 09:20:01", tz="UTC"),
        },
        false_signals={0: False, 1: False},
        equity_observations={0: 100_000.0, 1: 100_050.0},
        calibration_outcomes={0: 1.0, 1: 1.0},
        operational_events=2,
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-2026-09",
        code_version="abc123",
    )

    assert record.source_run_id == "paper-run-001"
    assert record.period_start == "2026-09-23T09:15:00+00:00"
    assert record.period_end == "2026-09-23T09:20:00+00:00"
    assert journal.records() == (record,)


def test_persist_rejects_empty_run(tmp_path: Path) -> None:
    journal = PaperEvidenceJournal(tmp_path / "paper_evidence.jsonl")

    with pytest.raises(ValueError, match="empty"):
        persist_paper_decision_run(
            SimpleNamespace(steps=()),
            journal=journal,
            source_run_id="paper-run-empty",
            evidence_version="PAPER-EVIDENCE-v1",
            dataset_version="paper-2026-09",
            code_version="abc123",
        )
