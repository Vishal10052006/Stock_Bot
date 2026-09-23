from types import SimpleNamespace

import pandas as pd

from experiments.paper_evidence import (
    PaperEvidenceCollector,
    collect_paper_decision_run,
    PaperEvidenceSnapshot,
    validate_paper_evidence,
)
from paper.runtime import PaperOrderStatus
from trading.strategy.models import StrategyDirection


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


def test_paper_evidence_collector_builds_snapshot_from_step() -> None:
    collector = PaperEvidenceCollector(
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-2026-09",
        code_version="abc123",
    )
    strategy = SimpleNamespace(
        direction=StrategyDirection.LONG,
        regime="TREND_UP",
        timestamp=pd.Timestamp("2026-09-23 09:15:00", tz="UTC"),
        prediction_probability=0.8,
    )
    order = SimpleNamespace(status=PaperOrderStatus.FILLED)
    step = SimpleNamespace(strategy=strategy, order=order)

    collector.record_step(
        step,
        fill_timestamp=pd.Timestamp("2026-09-23 09:15:02", tz="UTC"),
        false_signal=False,
        realized_equity=100_100.0,
        calibration_outcome=1.0,
    )
    collector.record_operational_event()

    snapshot = collector.snapshot()
    report = validate_paper_evidence(snapshot)

    assert report.valid
    assert snapshot.signal_count == 1
    assert snapshot.fill_count == 1
    assert snapshot.latency_observation_count == 1
    assert snapshot.drawdown_observation_count == 1
    assert snapshot.calibration_observation_count == 1
    assert snapshot.operational_event_count == 1


def test_paper_evidence_collector_rejects_backdated_fill() -> None:
    collector = PaperEvidenceCollector(
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-2026-09",
        code_version="abc123",
    )
    strategy = SimpleNamespace(
        direction=StrategyDirection.LONG,
        regime="TREND_UP",
        timestamp=pd.Timestamp("2026-09-23 09:15:00", tz="UTC"),
        prediction_probability=0.8,
    )
    order = SimpleNamespace(status=PaperOrderStatus.FILLED)

    import pytest

    with pytest.raises(ValueError, match="cannot precede"):
        collector.record_step(
            SimpleNamespace(strategy=strategy, order=order),
            fill_timestamp=pd.Timestamp("2026-09-23 09:14:59", tz="UTC"),
        )


def test_paper_run_adapter_preserves_explicit_operational_counts() -> None:
    strategy = SimpleNamespace(
        direction=StrategyDirection.LONG,
        regime="TREND_UP",
        timestamp=pd.Timestamp("2026-09-23 09:15:00", tz="UTC"),
        prediction_probability=0.8,
    )
    order = SimpleNamespace(status=PaperOrderStatus.FILLED)
    run = SimpleNamespace(
        steps=(SimpleNamespace(strategy=strategy, order=order),),
    )

    snapshot = collect_paper_decision_run(
        run,
        fill_timestamps={
            0: pd.Timestamp("2026-09-23 09:15:01", tz="UTC"),
        },
        false_signals={0: False},
        equity_observations={0: 100_000.0},
        calibration_outcomes={0: 1.0},
        operational_events=2,
        operational_errors=1,
        stale_events=1,
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-2026-09",
        code_version="abc123",
    )

    assert snapshot.operational_event_count == 2
    assert snapshot.operational_error_count == 1
    assert snapshot.stale_event_count == 1
    assert validate_paper_evidence(snapshot).valid
