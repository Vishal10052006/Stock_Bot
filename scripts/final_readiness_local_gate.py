#!/usr/bin/env python3
"""Run the remaining local/external evidence gates for STOCK_BOT.

This script is intentionally fail-closed. It verifies repository-side gates,
checks for the required persisted paper evidence, runs the paper-soak and
monitoring completion validators when their inputs exist, and reports the
remaining Upstox/provider evidence requirements without inventing any result.

It never enables live trading and never submits a broker order.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(command: list[str]) -> dict[str, object]:
    """Run one command and preserve its stdout/stderr for operator review."""
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _find_latest_session(root: Path) -> Path | None:
    """Return the newest persisted virtual-paper session, if any."""
    if not root.is_dir():
        return None
    sessions = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return sessions[0] if sessions else None


def main() -> int:
    """Evaluate all locally actionable evidence gates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="STOCK_BOT repository root",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        help="specific persisted virtual-paper session to validate",
    )
    parser.add_argument(
        "--required-soak-hours",
        type=float,
        default=6.0,
        help="minimum observed market-session hours required for CERT-08",
    )
    parser.add_argument(
        "--max-gap-minutes",
        type=float,
        default=10.0,
        help="maximum allowed observation gap for CERT-08 cadence validation",
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    results: dict[str, object] = {
        "live_locked": True,
        "repository_root": str(root),
    }

    # Repository-side readiness audit. This is expected to remain BLOCKED
    # whenever CERT-08/CERT-12 evidence is incomplete.
    results["module10_audit"] = _run(
        [sys.executable, "scripts/audit_module10_readiness.py", "--json"]
    )

    # CERT-08 can only be evaluated from persisted paper-session artifacts.
    session_dir = args.session_dir
    if session_dir is None:
        session_dir = _find_latest_session(root / "paper" / "virtual_sessions")

    if session_dir is None:
        results["cert08"] = {
            "status": "PENDING",
            "reason": "no persisted virtual-paper session directory was found",
        }
    else:
        soak_output = root / "paper" / "soak_evidence" / "CERT08-local-gate.json"
        soak_output.parent.mkdir(parents=True, exist_ok=True)
        results["cert08"] = _run(
            [
                sys.executable,
                "scripts/cert08_paper_soak.py",
                str(session_dir),
                "--required-hours",
                str(args.required_soak_hours),
                "--max-gap-minutes",
                str(args.max_gap_minutes),
                "--output",
                str(soak_output),
            ]
        )

    # M-24 uses the authoritative empirical paper report. It should only be
    # promoted by an actual PASS from its own validator.
    # Use -m so the repository root is on sys.path; direct execution of the
    # thin wrapper cannot resolve the top-level monitoring package reliably.
    results["monitoring_m24"] = _run(
        [
            sys.executable,
            "-m",
            "scripts.trading.validate_monitoring_completion",
        ]
    )

    # Provider evidence is intentionally not inferred from tests or docs.
    # The operator must collect the real observations in the supported environment.
    results["provider_evidence"] = {
        "status": "PENDING",
        "reason": (
            "CERT-12 requires real provider observations that cannot be "
            "fabricated or inferred from unit tests"
        ),
        "required": [
            "sandbox order_history (or documented provider block)",
            "sandbox partial_fill",
            "sandbox rate_limit",
            "sandbox timeout_recovery",
            "sandbox process_restart",
            "production read-only position_reconciliation",
        ],
    }

    results["live_execution"] = {
        "status": "LOCKED",
        "reason": "this gate never enables live broker execution",
    }

    print(json.dumps(results, indent=2, sort_keys=True))

    # Return non-zero whenever any evidence-gated command fails. The operator
    # can then inspect the exact failed gate without losing the safety lock.
    command_failures = [
        value
        for value in results.values()
        if isinstance(value, dict)
        and value.get("returncode") not in (None, 0)
    ]

    # Missing empirical/provider evidence is a blocking readiness condition,
    # but it is not a software failure. Keep the process fail-closed without
    # misclassifying an evidence gap as a command error.
    cert08_pending = (
        results.get("cert08", {}).get("status") == "PENDING"
        if isinstance(results.get("cert08"), dict)
        else False
    )
    # A completed repository-side audit may still report evidence blockers.
    # Returning non-zero is reserved for an actual failed validation command
    # or missing local paper-session input needed for CERT-08.
    return 1 if command_failures or cert08_pending else 0


if __name__ == "__main__":
    raise SystemExit(main())