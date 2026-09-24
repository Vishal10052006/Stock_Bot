"""Run the locked final OOS return-forecast evaluation.

This is the final external-test evidence gate after walk-forward validation.
The script does not tune hyperparameters, select a model, or alter the
chronological split. Both pre-declared baseline model families can be scored
for descriptive evidence; their test metrics must not be used to retroactively
change the protocol.

The external test is never passed to fit(), conformal calibrate(), or any
preprocessing fit operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from scripts.run_phase9_return_forecast_experiment import (
    _chronological_split,
    _prepare_features,
    _split_train_for_calibration,
    _run_model,
)
from market.features.builder import FEATURE_COLUMNS


FROZEN_MODELS = ("ridge", "random_forest")
FROZEN_PURGE_MINUTES = 60
FROZEN_TRAIN_RATIO = 0.70
FROZEN_VALIDATION_RATIO = 0.15
FROZEN_CALIBRATION_RATIO = 0.10
FROZEN_CONFIDENCE = 0.90


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_merged(dataset_path: Path, target_path: Path) -> tuple[pd.DataFrame, list[str], int]:
    dataset = pd.read_parquet(dataset_path)
    targets = pd.read_parquet(target_path)

    dataset["timestamp"] = pd.to_datetime(dataset["timestamp"], errors="raise")
    targets["timestamp"] = pd.to_datetime(targets["timestamp"], errors="raise")

    if not isinstance(dataset["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("dataset timestamps must be timezone-aware")
    if not isinstance(targets["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("target timestamps must be timezone-aware")

    required = {
        "timestamp",
        "symbol",
        "future_timestamp",
        "future_return",
        "horizon_bars",
    }
    missing = required.difference(targets.columns)
    if missing:
        raise ValueError(f"targets missing required columns: {sorted(missing)}")

    horizons = targets["horizon_bars"].dropna().astype(int).unique()
    if len(horizons) != 1 or int(horizons[0]) < 1:
        raise ValueError("target artifact must contain exactly one positive horizon")

    feature_columns = [
        column for column in FEATURE_COLUMNS if column in dataset.columns
    ]
    if not feature_columns:
        raise ValueError("No canonical Phase 5 feature columns are present")

    merged = dataset.merge(
        targets[
            [
                "timestamp",
                "symbol",
                "future_timestamp",
                "future_return",
                "horizon_bars",
            ]
        ],
        on=["timestamp", "symbol"],
        how="inner",
        validate="one_to_one",
    )
    if merged.empty:
        raise ValueError("No feature/return-target observations overlap")

    merged["future_timestamp"] = pd.to_datetime(
        merged["future_timestamp"], errors="raise"
    )
    if not (merged["future_timestamp"] > merged["timestamp"]).all():
        raise ValueError("Return target contains a non-future timestamp")

    merged = merged.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    return merged, feature_columns, int(horizons[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--model-family",
        choices=(*FROZEN_MODELS, "both"),
        default="both",
        help="Pre-declared family to score; 'both' reports descriptive OOS evidence without selection.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    target_path = Path(args.targets)
    out_path = Path(args.out)

    merged, feature_columns, horizon = _load_merged(dataset_path, target_path)
    train, validation, test, boundaries = _chronological_split(
        merged,
        train_ratio=FROZEN_TRAIN_RATIO,
        validation_ratio=FROZEN_VALIDATION_RATIO,
        purge_minutes=FROZEN_PURGE_MINUTES,
    )
    fit, calibration = _split_train_for_calibration(
        train,
        calibration_ratio=FROZEN_CALIBRATION_RATIO,
    )

    selected = FROZEN_MODELS if args.model_family == "both" else (args.model_family,)

    print("=" * 72)
    print("PHASE 9 — FINAL LOCKED OOS RETURN FORECAST")
    print("=" * 72)
    print(f"Observations: {len(merged)}")
    print(f"Fit={len(fit)}, calibration={len(calibration)}, validation={len(validation)}, final OOS={len(test)}")
    print(f"Target horizon: {horizon} bars")
    print(f"Frozen model family selection: {args.model_family}")
    print(f"Boundaries: {boundaries}")

    results = {
        "status": "FINAL_OOS_EVIDENCE",
        "selection_policy": (
            "Final OOS metrics are descriptive evidence only. They are not "
            "used to tune hyperparameters, choose a model family, or modify the protocol."
        ),
        "protocol": {
            "train_ratio": FROZEN_TRAIN_RATIO,
            "validation_ratio": FROZEN_VALIDATION_RATIO,
            "test_ratio": 1.0 - FROZEN_TRAIN_RATIO - FROZEN_VALIDATION_RATIO,
            "purge_minutes": FROZEN_PURGE_MINUTES,
            "calibration_ratio_within_train": FROZEN_CALIBRATION_RATIO,
            "confidence": FROZEN_CONFIDENCE,
            "horizon_bars": horizon,
            "external_test_used_for_model_selection": False,
            "preprocessing_fit_on_final_test": False,
            "calibration_fit_on_final_test": False,
        },
        "artifacts": {
            "dataset": str(dataset_path),
            "dataset_sha256": _sha256_file(dataset_path),
            "targets": str(target_path),
            "targets_sha256": _sha256_file(target_path),
        },
        "counts": {
            "merged": len(merged),
            "fit": len(fit),
            "calibration": len(calibration),
            "validation": len(validation),
            "final_oos": len(test),
        },
        "boundaries": boundaries,
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "models": {},
    }

    for family in selected:
        result = _run_model(
            family=family,
            fit=fit,
            calibration=calibration,
            validation=validation,
            test=test,
            feature_columns=feature_columns,
            confidence=FROZEN_CONFIDENCE,
        )
        results["models"][family] = result
        point = result["test"]["point_forecast"]
        interval = result["test"]["interval"]
        print(
            f"{family}: final OOS MAE={point['mae']:.8f} "
            f"RMSE={point['rmse']:.8f} "
            f"direction={point['directional_accuracy']:.4f} "
            f"coverage={interval['empirical_coverage']:.4f}"
        )

    out_path.write_text(json.dumps(results, indent=2))
    print(f"Final OOS artifact: {out_path}")


if __name__ == "__main__":
    main()
