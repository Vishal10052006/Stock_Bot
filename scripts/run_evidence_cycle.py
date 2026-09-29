"""Validate one explicit Phase-9 evidence cycle and emit an immutable manifest.

This command only consumes artifacts that already exist. It never invents
OOS, walk-forward, paper, or promotion evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from self_learning.evidence_runner import REQUIRED_STAGES
from self_learning.provenance import build_phase9_dataset_version
from self_learning.real_dataset import inspect_phase9_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Explicit Phase-9 parquet snapshot.")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--feature-schema-version", required=True)
    parser.add_argument("--label-definition-version", required=True)
    parser.add_argument(
        "--out",
        default="data/research/evidence_cycle_manifest.json",
        help="Manifest output path.",
    )
    args = parser.parse_args()

    path = Path(args.dataset)
    diagnostics = inspect_phase9_snapshot(path)
    dataset_version = build_phase9_dataset_version(
        path,
        dataset_version=args.dataset_version,
        source=args.source,
        creation_timestamp=args.created_at,
        feature_schema_version=args.feature_schema_version,
        label_definition_version=args.label_definition_version,
    )

    manifest = {
        "status": "DATASET_VERIFIED",
        "dataset": {
            "version": dataset_version.dataset_version,
            "fingerprint": dataset_version.fingerprint,
            "source": dataset_version.source,
            "rows": dataset_version.row_count,
            "symbols": list(dataset_version.symbols),
            "period_start": dataset_version.period_start,
            "period_end": dataset_version.period_end,
            "label_distribution": dict(dataset_version.label_distribution),
            "known_limitations": list(dataset_version.known_limitations),
        },
        "snapshot_diagnostics": {
            "path": diagnostics.source_path,
            "feature_columns": list(diagnostics.feature_columns),
            "duplicate_key_count": diagnostics.duplicate_key_count,
            "missing_counts": dict(diagnostics.missing_counts),
            "missing_rate_by_column": dict(diagnostics.missing_rate_by_column),
        },
        "required_evidence_stages": list(REQUIRED_STAGES),
        "evidence_status": {
            stage: "REQUIRED_ARTIFACT_NOT_SUPPLIED"
            for stage in REQUIRED_STAGES
        },
        "promotion_status": "NOT_REVIEWED",
        "live_execution": "LOCKED",
    }

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
