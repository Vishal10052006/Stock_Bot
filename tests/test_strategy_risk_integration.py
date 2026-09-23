"""Integration tests for Strategy -> Candidate -> Risk -> Paper/Backtest."""

from __future__ import annotations

import pandas as pd

from experiments.paper_journal import PaperEvidenceJournal

from backtesting.engine import HistoricalBacktestEngine
from trading.paper.decision_loop import PaperDecisionLoop


def risk_row(timestamp: str) -> dict[str, object]:
    """Create a complete causal row for strategy, candidate and risk."""
    return {
        "timestamp": pd.Timestamp(timestamp, tz="UTC"),
        "symbol": "RELIANCE",
        "close": 100.0,
        "atr_14": 2.0,
        "swing_low": 96.0,
        "swing_high": 104.0,
        "support_20": 95.0,
        "resistance_20": 105.0,
        "regime": "TREND_UP",
        "regime_probability": 0.90,
        "vwap_distance_pct": 0.5,
        "rvol_20": 1.4,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }


def test_paper_uses_risk_engine_position_size() -> None:
    """Paper execution quantity must come from risk-first sizing."""
    rows = pd.DataFrame(
        [
            risk_row("2026-09-21 10:00:00"),
            risk_row("2026-09-21 10:05:00"),
        ]
    )

    result = PaperDecisionLoop().run(rows)

    assert result.orders
    assert result.orders[0].quantity == 166.0
    assert result.steps[0].risk.status.value == "APPROVED"


def test_paper_blocks_duplicate_open_symbol() -> None:
    """Risk must reject a second entry while the symbol remains open."""
    rows = pd.DataFrame(
        [
            risk_row("2026-09-21 10:00:00"),
            risk_row("2026-09-21 10:05:00"),
        ]
    )

    result = PaperDecisionLoop().run(rows)

    assert result.steps[1].risk.status.value == "REJECTED"
    assert "already has an open position" in result.steps[1].risk.reason


def test_backtest_uses_risk_engine_position_size() -> None:
    """Historical replay must use RiskEngine sizing before paper execution."""
    rows = pd.DataFrame(
        [
            risk_row("2026-09-21 10:00:00"),
            risk_row("2026-09-21 10:05:00"),
            risk_row("2026-09-21 11:05:00"),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    assert result.orders
    assert result.orders[0].quantity == 166.0
    assert result.steps[0].risk.status.value == "APPROVED"


def test_paper_run_has_deterministic_identity_and_persists_evidence(tmp_path) -> None:
    """The paper boundary must bind evidence to the completed run identity."""
    rows = pd.DataFrame(
        [
            risk_row("2026-09-21 10:00:00"),
            risk_row("2026-09-21 10:05:00"),
        ]
    )
    journal = PaperEvidenceJournal(tmp_path / "paper_evidence.jsonl")

    loop = PaperDecisionLoop()
    run, record = loop.run_and_persist_evidence(
        rows,
        journal=journal,
        fill_timestamps={0: pd.Timestamp("2026-09-21 10:00:01", tz="UTC")},
        false_signals={0: False, 1: True},
        equity_observations={0: 100_000.0},
        calibration_outcomes={0: 1.0},
        operational_events=2,
        evidence_version="PAPER-EVIDENCE-v1",
        dataset_version="paper-test-v1",
        code_version="test-code-v1",
    )

    assert run.run_id == record.source_run_id
    assert run.run_id == loop.run(rows).run_id
    assert journal.records() == (record,)
