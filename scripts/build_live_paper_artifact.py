"""Build the trusted Phase-9 Logistic model bundle for live PAPER inference.

This command trains only from an explicitly selected, local Phase-9 dataset
snapshot, serializes the fitted LogisticOutcomeModel + FeaturePreprocessor,
and writes the SHA-256-bound manifest required by LiveModelRuntime.

Real market datasets and model bytes remain local/git-ignored.
No model promotion and no broker authority are performed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import pandas as pd

from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import TemporalSplitConfig, temporal_split
from ml.prediction.contracts import PredictionProvenance
from ml.prediction.live_bundle import load_live_prediction_bundle, save_live_prediction_bundle
from ml.training import train_baseline
from market.features.builder import FEATURE_COLUMNS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = ROOT / "data" / "research"
DEFAULT_ARTIFACT = ROOT / "data" / "models" / "live_prediction_bundle.pkl"


def _git_version() -> str:
    """Return the exact source revision used to build the artifact."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("cannot determine git code version") from exc


def _discover_dataset(directory: Path) -> Path:
    """Select the newest Phase-9 dataset snapshot deterministically."""
    paths = sorted(directory.glob("phase9_dataset_*.parquet"))
    if not paths:
        raise FileNotFoundError(
            f"no Phase-9 dataset snapshots found in {directory}"
        )
    return paths[-1]


def _load_dataset(path: Path) -> TrainingDataset:
    """Load and validate the frozen Phase-9 feature/label schema."""
    data = pd.read_parquet(path)
    required = {"timestamp", "symbol", "label", *FEATURE_COLUMNS}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            f"dataset is missing required columns: {sorted(missing)}"
        )

    data = data.loc[
        :,
        ["timestamp", "symbol", *FEATURE_COLUMNS, "label"],
    ].copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    return TrainingDataset(
        data=data.reset_index(drop=True),
        feature_columns=FEATURE_COLUMNS,
    )


def build_bundle(dataset_path: Path, artifact_path: Path) -> dict[str, object]:
    """Train, persist, reload, and verify one live-paper inference bundle."""
    dataset = _load_dataset(dataset_path)
    training = train_baseline(dataset)

    code_version = _git_version()
    provenance = PredictionProvenance(
        model_version="phase9-logistic-v1",
        model_family="logistic",
        dataset_version=dataset_path.stem,
        feature_version="phase9-features-v1",
        target_version="phase9-labels-v1",
        code_version=code_version,
        calibration_version="isotonic-v1",
    )

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = save_live_prediction_bundle(
        artifact_path,
        model=training.model,
        preprocessor=training.preprocessor,
        provenance=provenance,
        created_at=created_at,
    )

    # Immediate round-trip verification catches serialization or provenance
    # mismatches before the dashboard is allowed to start the session.
    bundle, verified_manifest = load_live_prediction_bundle(
        artifact_path,
        expected_sha256=manifest.artifact_sha256,
    )

    split = temporal_split(dataset, config=TemporalSplitConfig())

    report = {
        "artifact": str(artifact_path),
        "manifest": str(
            artifact_path.with_suffix(artifact_path.suffix + ".json")
        ),
        "artifact_sha256": verified_manifest.artifact_sha256,
        "model_version": bundle.provenance.model_version,
        "model_family": bundle.provenance.model_family,
        "dataset_version": bundle.provenance.dataset_version,
        "feature_version": bundle.provenance.feature_version,
        "target_version": bundle.provenance.target_version,
        "code_version": bundle.provenance.code_version,
        "calibration_version": bundle.provenance.calibration_version,
        "dataset_rows": len(dataset.data),
        "train_rows": training.train_rows,
        "calibration_rows": training.calibration_rows,
        "validation_rows": training.validation_rows,
        "test_rows": training.test_rows,
        "validation_start": split.validation_start.isoformat(),
        "validation_end": split.validation_end.isoformat(),
        "test_start": split.test_start.isoformat(),
        "broker_orders": 0,
        "trading_authority": "NONE",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Exact Phase-9 parquet snapshot. Defaults to newest local snapshot.",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help="Output fitted live-paper bundle path.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )
    args = parser.parse_args()

    dataset_path = args.dataset or _discover_dataset(DEFAULT_DATASET_DIR)
    if not dataset_path.is_file():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")

    report = build_bundle(dataset_path, args.artifact)

    report_path = args.report
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    print("=" * 72)
    print("PHASE 9 — LIVE PAPER ARTIFACT BUILT")
    print("=" * 72)
    for key in (
        "dataset_version",
        "model_version",
        "feature_version",
        "target_version",
        "artifact_sha256",
        "dataset_rows",
        "train_rows",
        "calibration_rows",
        "validation_rows",
        "test_rows",
    ):
        print(f"{key:24s} = {report[key]}")
    print(f"artifact                 = {report['artifact']}")
    print(f"manifest                 = {report['manifest']}")
    print("broker_orders            = 0")
    print("trading_authority        = NONE")
    if report_path is not None:
        print(f"report                   = {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
