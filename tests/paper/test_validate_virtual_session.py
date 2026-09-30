from __future__ import annotations

import hashlib
import json

import pytest

from scripts.validate_virtual_session import validate_session


def _write_session(tmp_path, *, open_positions=0, unrealized_pnl=0.0):
    session_dir = tmp_path / "SESSION-001"
    session_dir.mkdir()

    ledger = [
        {
            "timestamp": "2026-09-30T09:20:00+05:30",
            "equity": 100000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "gross_exposure": 0.0,
            "open_positions": 0,
        },
        {
            "timestamp": "2026-09-30T15:25:00+05:30",
            "equity": 100050.0,
            "realized_pnl": 50.0,
            "unrealized_pnl": unrealized_pnl,
            "gross_exposure": 0.0,
            "open_positions": open_positions,
        },
    ]
    ledger_path = session_dir / "account_ledger.jsonl"
    ledger_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in ledger),
        encoding="utf-8",
    )

    summary = {
        "session_id": "SESSION-001",
        "initial_equity": 100000.0,
        "final_equity": 100050.0,
        "realized_pnl": 50.0,
        "unrealized_pnl": unrealized_pnl,
        "gross_exposure": 0.0,
        "open_positions": open_positions,
        "completed_trades": 1,
        "live_broker_orders": 0,
        "account_ledger": str(ledger_path),
    }
    canonical = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    summary["fingerprint"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    (session_dir / "account_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return session_dir


def test_validate_virtual_session_passes_consistent_account(tmp_path):
    session_dir = _write_session(tmp_path)

    result = validate_session(session_dir)

    assert result["status"] == "PASS"
    assert result["ledger_rows"] == 2
    assert result["final_equity"] == 100050.0


@pytest.mark.parametrize(
    ("open_positions", "unrealized_pnl", "message"),
    [
        (1, 0.0, "final virtual account still has open positions"),
        (0, 1.0, "final virtual account has non-zero unrealized P&L"),
    ],
)
def test_validate_virtual_session_rejects_unclosed_account(
    tmp_path,
    open_positions,
    unrealized_pnl,
    message,
):
    session_dir = _write_session(
        tmp_path,
        open_positions=open_positions,
        unrealized_pnl=unrealized_pnl,
    )

    with pytest.raises(ValueError, match=message):
        validate_session(session_dir)


def test_validate_virtual_session_rejects_broker_orders(tmp_path):
    session_dir = _write_session(tmp_path)
    summary_path = session_dir / "account_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["live_broker_orders"] = 1
    summary.pop("fingerprint")
    summary["fingerprint"] = hashlib.sha256(
        json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(ValueError, match="live broker orders"):
        validate_session(session_dir)


def test_validate_virtual_session_rejects_fingerprint_mismatch(tmp_path):
    session_dir = _write_session(tmp_path)
    summary_path = session_dir / "account_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["final_equity"] = 100050.0
    summary["fingerprint"] = "0" * 64
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_session(session_dir)
