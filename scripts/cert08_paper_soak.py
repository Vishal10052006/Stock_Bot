#!/usr/bin/env python3
"""CERT-08 paper-soak evidence harness.

This command operates only on already-produced paper-session artifacts. It does
not place broker orders and it does not convert a short run into long-duration
evidence. A certification record is emitted only when the requested soak
duration is actually covered by the persisted session window.

Usage:
    python scripts/cert08_paper_soak.py \
        paper/virtual_sessions/CERT08-SESSION \
        --required-hours 6 \
        --output paper/soak_evidence/CERT08-SESSION.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

from scripts.validate_virtual_session import validate_session


def _load_ledger(session_dir: Path) -> list[dict[str, object]]:
    path = session_dir / "account_ledger.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"missing account ledger: {path}")
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("account ledger is empty")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("account ledger rows must be JSON objects")
    return rows


def build_cert08_evidence(
    session_dir: Path,
    *,
    required_hours: float,
) -> dict[str, object]:
    """Validate a session and emit an explicit duration-based evidence record."""
    if required_hours <= 0:
        raise ValueError("required_hours must be positive")

    validation = validate_session(session_dir)
    rows = _load_ledger(session_dir)

    timestamps = pd.to_datetime(
        [row["timestamp"] for row in rows],
        utc=True,
        errors="raise",
    )
    start = timestamps.min()
    end = timestamps.max()
    duration = end - start
    required = timedelta(hours=float(required_hours))

    payload = {
        "evidence_kind": "CERT-08-PAPER-SOAK",
        "status": "PASS" if duration >= required else "PARTIAL",
        "session_id": validation["session_id"],
        "session_dir": str(session_dir),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "observed_duration_seconds": duration.total_seconds(),
        "required_duration_seconds": required.total_seconds(),
        "ledger_rows": validation["ledger_rows"],
        "completed_trades": validation["completed_trades"],
        "final_equity": validation["final_equity"],
        "realized_pnl": validation["realized_pnl"],
        "live_broker_orders": validation["live_broker_orders"],
        "validator_status": validation["status"],
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--required-hours", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_cert08_evidence(
        args.session_dir,
        required_hours=args.required_hours,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
