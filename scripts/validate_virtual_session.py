#!/usr/bin/env python3
"""Validate one STOCK_BOT virtual intraday account session.

This validator checks persisted account invariants only. It does not execute
trades, contact a broker, or infer profitability.

Usage:
    python scripts/validate_virtual_session.py \
        paper/virtual_sessions/VIRTUAL-INTRADAY-001
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


def _load_json(path: Path) -> dict:
    """Load a JSON object and fail closed on malformed input."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_session(session_dir: Path) -> dict[str, object]:
    """Validate ledger, summary, and deterministic account invariants."""
    summary_path = session_dir / "account_summary.json"
    ledger_path = session_dir / "account_ledger.jsonl"

    summary = _load_json(summary_path)
    if not ledger_path.exists():
        raise FileNotFoundError(f"missing account ledger: {ledger_path}")

    if summary.get("live_broker_orders") != 0:
        raise ValueError("virtual session contains non-zero live broker orders")

    initial_equity = float(summary["initial_equity"])
    final_equity = float(summary["final_equity"])
    realized_pnl = float(summary["realized_pnl"])
    unrealized_pnl = float(summary["unrealized_pnl"])

    numeric_values = (
        initial_equity,
        final_equity,
        realized_pnl,
        unrealized_pnl,
        float(summary["gross_exposure"]),
    )
    if not all(math.isfinite(value) for value in numeric_values):
        raise ValueError("summary contains non-finite account values")

    rows: list[dict] = []
    for line_number, line in enumerate(
        ledger_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"ledger line {line_number} is not a JSON object")
        rows.append(row)

    if not rows:
        raise ValueError("account ledger is empty")

    timestamps = pd.to_datetime(
        [row["timestamp"] for row in rows],
        utc=True,
        errors="raise",
    )
    if not timestamps.is_monotonic_increasing:
        raise ValueError("account ledger timestamps are not chronological")
    if timestamps.duplicated().any():
        raise ValueError("account ledger contains duplicate timestamps")

    for index, row in enumerate(rows, start=1):
        for field in (
            "equity",
            "realized_pnl",
            "unrealized_pnl",
            "gross_exposure",
        ):
            value = float(row[field])
            if not math.isfinite(value):
                raise ValueError(
                    f"ledger line {index} has non-finite {field}"
                )
        if float(row["gross_exposure"]) < 0:
            raise ValueError(f"ledger line {index} has negative gross exposure")
        if int(row["open_positions"]) < 0:
            raise ValueError(f"ledger line {index} has negative open positions")

    final = rows[-1]
    if int(final["open_positions"]) != 0:
        raise ValueError("final virtual account still has open positions")
    if abs(float(final["unrealized_pnl"])) > 1e-9:
        raise ValueError("final virtual account has non-zero unrealized P&L")

    expected_equity = (
        initial_equity
        + realized_pnl
        + unrealized_pnl
    )
    if not math.isclose(
        final_equity,
        expected_equity,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "final equity does not reconcile to initial equity + P&L"
        )

    ledger_summary_fields = {
        "final_equity": "equity",
        "realized_pnl": "realized_pnl",
        "unrealized_pnl": "unrealized_pnl",
        "gross_exposure": "gross_exposure",
        "open_positions": "open_positions",
    }
    for summary_field, ledger_field in ledger_summary_fields.items():
        if float(final[ledger_field]) != float(summary[summary_field]):
            raise ValueError(
                f"summary/{summary_field} does not match final ledger snapshot"
            )

    fingerprint_payload = dict(summary)
    fingerprint_payload.pop("fingerprint", None)
    canonical = json.dumps(
        fingerprint_payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected_fingerprint = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    if summary.get("fingerprint") != expected_fingerprint:
        raise ValueError("account summary fingerprint mismatch")

    return {
        "session_id": summary.get("session_id"),
        "status": "PASS",
        "ledger_rows": len(rows),
        "completed_trades": int(summary["completed_trades"]),
        "final_equity": final_equity,
        "realized_pnl": realized_pnl,
        "live_broker_orders": int(summary["live_broker_orders"]),
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate a STOCK_BOT virtual intraday session."
    )
    parser.add_argument("session_dir", type=Path)
    args = parser.parse_args()

    result = validate_session(args.session_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
