"""Export a verified Phase-9 Logistic inference artifact.

The exported payload contains the fitted model, fitted preprocessor, and
calibrator produced by the existing chronological Phase-9 training protocol.
No test partition is scored or used for fitting.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from market.features.builder import FEATURE_COLUMNS
from ml.datasets.models import TrainingDataset
from ml.prediction.artifacts import save_prediction_artifact
from ml.prediction.contracts import PredictionProvenance
from ml.training import train_baseline
from ml.training.models import TrainingConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a Phase-9 Logistic model/preprocessor artifact."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-version", default="phase9-logistic-v1")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--feature-version", default="v1.0")
    parser.add_argument("--target-version", default="phase7-decision-label-v1")
    parser.add_argument("--code-version", required=True)
    args = parser.parse_args()

    data = pd.read_parquet(args.dataset)
    required = {"timestamp", "symbol", "label", *FEATURE_COLUMNS}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"dataset is missing required columns: {missing}")

    data = data.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="raise")
    data["symbol"] = data["symbol"].astype(str).str.strip().str.upper()

    dataset = TrainingDataset(
        data=data.loc[
            :,
            ["timestamp", "symbol", *FEATURE_COLUMNS, "label"],
        ].copy(),
        feature_columns=FEATURE_COLUMNS,
    )

    result = train_baseline(dataset, config=TrainingConfig())

    provenance = PredictionProvenance(
        model_version=args.model_version,
        model_family="logistic",
        dataset_version=args.dataset_version,
        feature_version=args.feature_version,
        target_version=args.target_version,
        code_version=args.code_version,
        calibration_version="isotonic-v1",
    )

    manifest = save_prediction_artifact(
        args.output,
        model={
            "model": result.model,
            "preprocessor": result.preprocessor,
            "calibrator": result.calibrator,
        },
        provenance=provenance,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    print(f"artifact: {args.output}")
    print(f"sha256: {manifest.artifact_sha256}")
    print(f"model_version: {manifest.model_version}")
    print(f"train_rows: {result.train_rows}")
    print(f"calibration_rows: {result.calibration_rows}")
    print(f"validation_rows: {result.validation_rows}")
    print(f"test_rows: {result.test_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
