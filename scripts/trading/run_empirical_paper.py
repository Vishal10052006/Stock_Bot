"""Run one reproducible empirical paper-trading evidence job.

The input is a frozen, strategy-ready chronological parquet dataset. This command
does not manufacture observations that the PaperDecisionLoop cannot establish.
Optional evidence that exists outside the loop is supplied through a JSON sidecar.

Example:
    python scripts/trading/run_empirical_paper.py \
      --input data/paper/frozen_rows.parquet \
      --dataset-version paper-2026-09-v1 \
      --code-version <git-sha> \
      --evidence-version PAPER-EVIDENCE-v1 \
      --journal data/paper/paper_evidence.jsonl \
      --output data/paper/empirical_paper_report.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

# Direct script execution sets sys.path[0] to scripts/trading rather than
# the repository root. Bootstrap the repository root so imports such as
# `experiments.*` and `trading.*` resolve exactly as they do from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd

from experiments.paper_journal import PaperEvidenceJournal
from experiments.paper_quality import assess_paper_evidence
from trading.paper.decision_loop import PaperDecisionLoop


_REQUIRED_COLUMNS = {
    "timestamp",
    "symbol",
    "close",
    "regime",
    "regime_probability",
    "vwap_distance_pct",
    "rvol_20",
    "higher_high",
    "higher_low",
    "lower_low",
    "lower_high",
}


def _load_rows(path: str | Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    missing = sorted(_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"paper input is missing required columns: {missing}")
    if frame.empty:
        raise ValueError("paper input is empty")

    frame = frame.copy()
    raw_timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    if raw_timestamp.isna().any():
        raise ValueError("paper input contains invalid timestamps")

    frame["timestamp"] = raw_timestamp
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    if (frame["symbol"] == "").any():
        raise ValueError("paper input contains an empty symbol")

    if not raw_timestamp.is_monotonic_increasing:
        raise ValueError(
            "paper input must already be in chronological order; "
            "refusing to reorder empirical observations"
        )

    if frame.duplicated(["timestamp", "symbol"]).any():
        raise ValueError("paper input contains duplicate timestamp/symbol rows")

    return frame


def _load_sidecar(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evidence sidecar must be a JSON object")
    return payload


def _validate_non_negative_counts(
    operational_events: int | None,
    operational_errors: int,
    stale_events: int,
) -> None:
    if operational_events is not None and operational_events < 0:
        raise ValueError("operational_events must be non-negative")
    for name, value in (
        ("operational_errors", operational_errors),
        ("stale_events", stale_events),
    ):
        if value < 0:
            raise ValueError(f"{name} must be non-negative")


def _indexed_map(payload: dict[str, Any], name: str) -> dict[int, object]:
    value = payload.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object keyed by step index")
    result: dict[int, object] = {}
    for key, item in value.items():
        try:
            index = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{name} contains a non-integer step index: {key!r}"
            ) from exc
        if index < 0:
            raise ValueError(f"{name} contains a negative step index: {index}")
        result[index] = item
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Frozen strategy-ready parquet.")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--code-version", required=True)
    parser.add_argument("--evidence-version", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--observations-json", default=None)
    parser.add_argument("--price-column", default="close")
    parser.add_argument("--quantity", type=float, default=1.0)
    args = parser.parse_args()

    rows = _load_rows(args.input)
    sidecar = _load_sidecar(args.observations_json)

    operational_events = (
        int(sidecar["operational_events"])
        if "operational_events" in sidecar
        else None
    )
    operational_errors = int(sidecar.get("operational_errors", 0))
    stale_events = int(sidecar.get("stale_events", 0))
    _validate_non_negative_counts(
        operational_events,
        operational_errors,
        stale_events,
    )

    fill_timestamps = _indexed_map(sidecar, "fill_timestamps")
    false_signals = _indexed_map(sidecar, "false_signals")
    equity_observations = _indexed_map(sidecar, "equity_observations")
    calibration_outcomes = _indexed_map(sidecar, "calibration_outcomes")

    journal = PaperEvidenceJournal(args.journal)
    loop = PaperDecisionLoop()
    run, record = loop.run_and_persist_evidence(
        rows,
        journal=journal,
        price_column=args.price_column,
        quantity=args.quantity,
        fill_timestamps=fill_timestamps or None,
        false_signals=false_signals or None,
        equity_observations=equity_observations or None,
        calibration_outcomes=calibration_outcomes or None,
        operational_events=operational_events,
        operational_errors=operational_errors,
        stale_events=stale_events,
        evidence_version=args.evidence_version,
        dataset_version=args.dataset_version,
        code_version=args.code_version,
    )

    quality = assess_paper_evidence(journal.records())

    report = {
        "status": "EVIDENCE_VALIDATED" if quality.valid else "EVIDENCE_INCOMPLETE",
        "claim_boundary": (
            "This report records and validates empirical paper evidence only; "
            "it does not establish profitability or live-trading readiness."
        ),
        "input": {
            "path": str(Path(args.input)),
            "rows": len(rows),
            "symbols": sorted(rows["symbol"].unique().tolist()),
            "period_start": rows["timestamp"].min().isoformat(),
            "period_end": rows["timestamp"].max().isoformat(),
        },
        "paper_run": {
            "run_id": run.run_id,
            "steps": len(run.steps),
            "orders": len(run.orders),
        },
        "record": {
            "run_id": record.run_id,
            "fingerprint": record.fingerprint,
            "source_run_id": record.source_run_id,
            "evidence": (
                record.evidence.to_dict()
                if hasattr(record.evidence, "to_dict")
                else json.loads(record.evidence.canonical_json())
            ),
        },
        "observation_provenance": {
            "equity": (
                "paper_runtime_account_snapshot"
                if not equity_observations
                else "external_observation_sidecar"
            ),
            "latency": (
                "deterministic_paper_fill_timestamp"
                if run.orders and not fill_timestamps
                else (
                    "external_observation_sidecar"
                    if fill_timestamps
                    else "not_observed"
                )
            ),
            "operational_events": (
                "paper_decision_step"
                if "operational_events" not in sidecar
                else "external_observation_sidecar"
            ),
            "calibration": (
                "external_prediction_outcome_sidecar"
                if calibration_outcomes
                else "not_applicable_without_prediction_probability"
            ),
            "false_signal_outcomes": (
                "external_observation_sidecar"
                if false_signals
                else "not_observed"
            ),
        },
        "quality": {
            "valid": quality.valid,
            "issues": list(quality.issues),
            "records": quality.record_count,
        },
    }

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    print("=" * 72)
    print("STOCK BOT — EMPIRICAL PAPER EVIDENCE")
    print("=" * 72)
    print(f"Input rows           : {len(rows):,}")
    print(f"Paper run ID         : {run.run_id}")
    print(f"Paper steps          : {len(run.steps):,}")
    print(f"Paper orders         : {len(run.orders):,}")
    print(f"Evidence quality     : {'VALID' if quality.valid else 'INCOMPLETE'}")
    print(f"Quality issues       : {len(quality.issues):,}")
    print(
        "Calibration scope    : "
        + (
            "observed"
            if calibration_outcomes
            else "not applicable without prediction probability"
        )
    )
    print(f"Journal              : {args.journal}")
    print(f"Report               : {target}")
    print("=" * 72)


if __name__ == "__main__":
    main()
