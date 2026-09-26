from datetime import datetime, timezone

import pandas as pd
import pytest

from runtime.paper_session import PaperSession


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-09-25T09:15:00Z",
                "symbol": "ITC",
                "close": 500.0,
                "regime": "TREND",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 1.5,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
            },
            {
                "timestamp": "2026-09-25T09:20:00Z",
                "symbol": "ITC",
                "close": 501.0,
                "regime": "TREND",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 1.5,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
            },
        ]
    )


def test_phase22_requires_chronological_input(tmp_path) -> None:
    session = PaperSession.from_path(
        tmp_path / "paper.jsonl",
        session_id="phase22-test",
        code_version="test",
    )
    session.start(now=datetime(2026, 9, 25, 9, 15, tzinfo=timezone.utc))

    rows = _rows().iloc[::-1].reset_index(drop=True)

    with pytest.raises(ValueError, match="chronological"):
        session.run(rows)


def test_phase22_persists_one_immutable_evidence_record(tmp_path) -> None:
    path = tmp_path / "paper.jsonl"
    session = PaperSession.from_path(
        path,
        session_id="phase22-test",
        code_version="test",
    )
    result = session.run(_rows())

    assert result.evidence.run_id
    assert result.evidence.fingerprint
    assert result.summary()["live_broker_order_submission"] is False
    assert len(session.journal.records()) == 1


def test_phase22_rejects_duplicate_symbol_timestamp(tmp_path) -> None:
    rows = pd.concat([_rows().iloc[[0]], _rows().iloc[[0]]], ignore_index=True)
    session = PaperSession.from_path(
        tmp_path / "paper.jsonl",
        session_id="phase22-test",
        code_version="test",
    )

    with pytest.raises(ValueError, match="duplicate timestamp"):
        session.run(rows)
