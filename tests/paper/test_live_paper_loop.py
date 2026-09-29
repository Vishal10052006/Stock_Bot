"""Tests for LivePaperEngine and 10-trade controlled experiment."""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

from trading.paper.live_loop import (
    LivePaperEngine,
    LivePaperSessionConfig,
)
from scripts.trading.run_live_paper import generate_synthetic_stream


def test_10_trade_session_terminates_at_target(tmp_path: Path):
    """Verify that a live paper session stops automatically once 10 trades complete."""
    config = LivePaperSessionConfig(
        experiment_id="PAPER-TEST-10",
        target_trades=10,
        symbol="RELIANCE",
        output_dir=tmp_path,
        stop_on_target_trades=True,
    )
    engine = LivePaperEngine(config)

    # Generate 150 alternating candles to trigger multiple entries and exits
    candles = generate_synthetic_stream("RELIANCE", count=150)
    result = engine.run_candles(candles)

    # Must have completed at least target_trades and declared target_reached
    assert result.completed_trades >= 10
    assert result.target_reached is True
    assert result.metrics.total_trades >= 10
    assert len(result.session_fingerprint) == 64  # SHA-256 hex length


def test_session_evidence_bundle_persistence(tmp_path: Path):
    """Verify that the session writes all required immutable evidence files."""
    exp_id = "PAPER-EVIDENCE-TEST"
    config = LivePaperSessionConfig(
        experiment_id=exp_id,
        target_trades=3,
        symbol="RELIANCE",
        output_dir=tmp_path,
    )
    engine = LivePaperEngine(config)
    candles = generate_synthetic_stream("RELIANCE", count=60)
    result = engine.run_candles(candles)

    session_dir = tmp_path / exp_id
    assert session_dir.exists()

    # 1. session.json
    session_json = session_dir / "session.json"
    assert session_json.exists()
    session_data = json.loads(session_json.read_text(encoding="utf-8"))
    assert session_data["config"]["experiment_id"] == exp_id
    assert session_data["live_broker_orders"] == 0

    # 2. metrics.json
    metrics_json = session_dir / "metrics.json"
    assert metrics_json.exists()
    metrics_data = json.loads(metrics_json.read_text(encoding="utf-8"))
    assert "win_rate_pct" in metrics_data
    assert "net_pnl" in metrics_data

    # 3. report.txt
    report_txt = session_dir / "report.txt"
    assert report_txt.exists()
    report_content = report_txt.read_text(encoding="utf-8")
    assert "STOCK_BOT PAPER EXPERIMENT" in report_content

    # 4. outcomes.jsonl
    outcomes_jsonl = session_dir / "outcomes.jsonl"
    assert outcomes_jsonl.exists()

    # 5. session_fingerprint.sha256
    fingerprint_file = session_dir / "session_fingerprint.sha256"
    assert fingerprint_file.exists()
    assert fingerprint_file.read_text(encoding="utf-8").strip() == result.session_fingerprint
