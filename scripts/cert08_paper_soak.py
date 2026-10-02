#!/usr/bin/env python3
"""CERT-08 paper-soak evidence harness.

The harness validates already-produced virtual-session artifacts. It never
creates trades, contacts a broker, or fabricates duration/evidence.

One or more session directories can be supplied. For multiple trading days,
aggregate duration is the sum of each validated session's observed session
window; overnight time is never counted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

from scripts.validate_virtual_session import validate_session


def _session_paths(value: Path | Iterable[Path]) -> tuple[Path, ...]:
    """Normalize one or many session paths."""
    if isinstance(value, (str, Path)):
        return (Path(value),)
    return tuple(Path(item) for item in value)


def _load_ledger(session_dir: Path) -> list[dict[str, object]]:
    """Load one already-persisted account ledger."""
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


def _session_diagnostics(
    session_dir: Path,
    *,
    max_gap_minutes: float | None,
) -> dict[str, object]:
    """Validate and summarize one session's observed window and gaps."""
    validation = validate_session(session_dir)
    rows = _load_ledger(session_dir)
    timestamps = pd.to_datetime(
        [row["timestamp"] for row in rows],
        utc=True,
        errors="raise",
    )
    deltas = timestamps.to_series().diff().dropna()
    max_gap_seconds = (
        float(deltas.dt.total_seconds().max()) if not deltas.empty else 0.0
    )
    gap_violation = (
        max_gap_minutes is not None
        and max_gap_seconds > max_gap_minutes * 60.0
    )

    start = timestamps.min().isoformat()
    end = timestamps.max().isoformat()
    observed_duration_seconds = (
        timestamps.max() - timestamps.min()
    ).total_seconds()

    return {
        "session_id": validation["session_id"],
        "session_dir": str(Path(session_dir)),
        "start": start,
        "end": end,
        "observed_duration_seconds": observed_duration_seconds,
        "ledger_rows": validation["ledger_rows"],
        "completed_trades": validation["completed_trades"],
        "final_equity": validation["final_equity"],
        "realized_pnl": validation["realized_pnl"],
        "live_broker_orders": validation["live_broker_orders"],
        "max_gap_seconds": max_gap_seconds,
        "gap_violation": gap_violation,
        "validator_status": validation["status"],
    }


def build_cert08_evidence(
    session_dir: Path | Iterable[Path],
    *,
    required_hours: float,
    max_gap_minutes: float | None = None,
) -> dict[str, object]:
    """Build aggregate CERT-08 evidence from one or more real paper sessions."""
    if required_hours <= 0:
        raise ValueError("required_hours must be positive")
    if max_gap_minutes is not None and max_gap_minutes <= 0:
        raise ValueError("max_gap_minutes must be positive when supplied")

    sessions = _session_paths(session_dir)
    if not sessions:
        raise ValueError("at least one session directory is required")

    diagnostics = tuple(
        _session_diagnostics(path, max_gap_minutes=max_gap_minutes)
        for path in sessions
    )
    session_ids = [str(item["session_id"]) for item in diagnostics]
    if len(set(session_ids)) != len(session_ids):
        raise ValueError("duplicate session_id in CERT-08 campaign")

    total_duration = sum(
        float(item["observed_duration_seconds"]) for item in diagnostics
    )
    required = timedelta(hours=float(required_hours)).total_seconds()
    any_gap_violation = any(
        bool(item["gap_violation"]) for item in diagnostics
    )
    any_provider_orders = any(
        int(item["live_broker_orders"]) != 0 for item in diagnostics
    )

    payload = {
        "evidence_kind": "CERT-08-PAPER-SOAK",
        "status": (
            "PASS"
            if total_duration >= required
            and not any_gap_violation
            and not any_provider_orders
            else "PARTIAL"
        ),
        "session_count": len(diagnostics),
        "session_ids": session_ids,
        "sessions": list(diagnostics),
        "start": min(str(item["start"]) for item in diagnostics),
        "end": max(str(item["end"]) for item in diagnostics),
        "observed_duration_seconds": total_duration,
        "required_duration_seconds": required,
        "max_gap_minutes": max_gap_minutes,
        "live_broker_orders": sum(
            int(item["live_broker_orders"]) for item in diagnostics
        ),
        "ledger_rows": sum(int(item["ledger_rows"]) for item in diagnostics),
        "completed_trades": sum(
            int(item["completed_trades"]) for item in diagnostics
        ),
        "validator_status": "PASS",
        "cadence_status": "PARTIAL" if any_gap_violation else "PASS",
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["fingerprint"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return payload


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dirs", nargs="+", type=Path)
    parser.add_argument("--required-hours", type=float, required=True)
    parser.add_argument("--max-gap-minutes", type=float)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_cert08_evidence(
        args.session_dirs,
        required_hours=args.required_hours,
        max_gap_minutes=args.max_gap_minutes,
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
