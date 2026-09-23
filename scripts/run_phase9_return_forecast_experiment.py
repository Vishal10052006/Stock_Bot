"""Run a frozen chronological real-data return-forecast benchmark.

This script consumes:
  1. a frozen Phase 9 decision-feature parquet, and
  2. a separate causal fixed-horizon return-target parquet.

Protocol:
  - chronological 70/15/15 split with a 60-minute purge;
  - latest 10% of the training observations are calibration only;
  - model fitting and preprocessing use only the earlier training partition;
  - conformal interval calibration uses only the chronological calibration set;
  - validation and final test are scored without fitting/tuning on them.

The external test is evaluated for empirical evidence only. It is not used to
choose a model or hyperparameters.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from market.features.builder import FEATURE_COLUMNS  # noqa: E402
from ml.evaluation.return_forecast import (  # noqa: E402
    evaluate_prediction_intervals,
    evaluate_return_forecasts,
)
from ml.models.return_forecast import (  # noqa: E402
    ReturnForecastConfig,
    ReturnForecastModel,
)


def _chronological_split(
    frame: pd.DataFrame,
    *,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    purge_minutes: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]:
    timestamps = (
        frame["timestamp"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    if len(timestamps) < 3:
        raise ValueError("At least three unique timestamps are required.")

    train_index = max(1, int(len(timestamps) * train_ratio))
    validation_index = max(
        train_index + 1,
        int(len(timestamps) * (train_ratio + validation_ratio)),
    )
    validation_index = min(validation_index, len(timestamps) - 1)

    nominal_train_end = timestamps.iloc[train_index - 1]
    nominal_validation_end = timestamps.iloc[validation_index - 1]
    purge = timedelta(minutes=purge_minutes)

    train_end = nominal_train_end - purge
    validation_start = nominal_train_end + purge
    validation_end = nominal_validation_end - purge
    test_start = nominal_validation_end + purge

    train = frame.loc[frame["timestamp"] <= train_end].copy()
    validation = frame.loc[
        (frame["timestamp"] > validation_start)
        & (frame["timestamp"] <= validation_end)
    ].copy()
    test = frame.loc[frame["timestamp"] > test_start].copy()

    if train.empty or validation.empty or test.empty:
        raise ValueError(
            "Chronological split produced an empty partition: "
            f"train={len(train)}, validation={len(validation)}, test={len(test)}"
        )

    boundaries = {
        "train_end": train_end.isoformat(),
        "validation_start": validation_start.isoformat(),
        "validation_end": validation_end.isoformat(),
        "test_start": test_start.isoformat(),
    }
    return train, validation, test, boundaries


def _split_train_for_calibration(
    train: pd.DataFrame,
    *,
    calibration_ratio: float = 0.10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    timestamps = (
        train["timestamp"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    split_index = max(1, int(len(timestamps) * (1.0 - calibration_ratio)))
    split_index = min(split_index, len(timestamps) - 1)
    boundary = timestamps.iloc[split_index - 1]

    fit = train.loc[train["timestamp"] <= boundary].copy()
    calibration = train.loc[train["timestamp"] > boundary].copy()

    if fit.empty or calibration.empty:
        raise ValueError("Training/calibration split produced an empty partition.")
    return fit, calibration


def _prepare_features(
    fit: pd.DataFrame,
    other_frames: list[pd.DataFrame],
    feature_columns: list[str],
    *,
    scale: bool,
) -> tuple[np.ndarray, list[np.ndarray]]:
    imputer = SimpleImputer(strategy="median")
    fit_values = imputer.fit_transform(fit[feature_columns])

    transformed = [
        imputer.transform(frame[feature_columns])
        for frame in other_frames
    ]

    if scale:
        scaler = StandardScaler()
        fit_values = scaler.fit_transform(fit_values)
        transformed = [scaler.transform(values) for values in transformed]

    return fit_values, transformed


def _run_model(
    *,
    family: str,
    fit: pd.DataFrame,
    calibration: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    feature_columns: list[str],
    confidence: float,
) -> dict:
    scale = family == "ridge"
    X_fit, [X_cal, X_val, X_test] = _prepare_features(
        fit,
        [calibration, validation, test],
        feature_columns,
        scale=scale,
    )

    model = ReturnForecastModel(
        ReturnForecastConfig(model_family=family)
    )
    model.fit(X_fit, fit["future_return"])
    model.calibrate(
        X_cal,
        calibration["future_return"],
        confidence=confidence,
    )

    predictions = {
        "validation": model.predict(X_val),
        "test": model.predict(X_test),
    }

    metrics: dict[str, object] = {
        "model_family": family,
        "feature_count": len(feature_columns),
        "calibration_confidence": confidence,
        "conformal_radius": model.conformal_radius,
    }

    for partition, predicted, frame in (
        ("validation", predictions["validation"], validation),
        ("test", predictions["test"], test),
    ):
        actual = frame["future_return"].to_numpy(dtype=float)
        metrics[partition] = {
            "point_forecast": evaluate_return_forecasts(actual, predicted),
        }

        lower, upper = model.predict_interval(
            X_val if partition == "validation" else X_test
        )
        metrics[partition]["interval"] = evaluate_prediction_intervals(
            actual,
            lower,
            upper,
            confidence_level=confidence,
        )

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--confidence", type=float, default=0.90)
    args = parser.parse_args()

    dataset = pd.read_parquet(args.dataset)
    targets = pd.read_parquet(args.targets)

    dataset["timestamp"] = pd.to_datetime(dataset["timestamp"], errors="raise")
    targets["timestamp"] = pd.to_datetime(targets["timestamp"], errors="raise")

    if not isinstance(dataset["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("dataset timestamps must be timezone-aware")
    if not isinstance(targets["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("target timestamps must be timezone-aware")

    required_targets = {
        "timestamp",
        "symbol",
        "future_timestamp",
        "future_return",
    }
    missing = required_targets.difference(targets.columns)
    if missing:
        raise ValueError(f"targets missing required columns: {sorted(missing)}")

    feature_columns = [
        column for column in FEATURE_COLUMNS if column in dataset.columns
    ]
    if not feature_columns:
        raise ValueError("No canonical Phase 5 feature columns are present.")

    merged = dataset.merge(
        targets[
            [
                "timestamp",
                "symbol",
                "future_timestamp",
                "future_return",
            ]
        ],
        on=["timestamp", "symbol"],
        how="inner",
        validate="one_to_one",
    )

    if merged.empty:
        raise ValueError("No feature/return-target observations overlap.")

    merged["future_timestamp"] = pd.to_datetime(
        merged["future_timestamp"],
        errors="raise",
    )
    if not (
        merged["future_timestamp"] > merged["timestamp"]
    ).all():
        raise ValueError("Return target contains a non-future timestamp.")

    merged = merged.sort_values(
        ["timestamp", "symbol"],
        kind="stable",
    ).reset_index(drop=True)

    train, validation, test, boundaries = _chronological_split(merged)
    fit, calibration = _split_train_for_calibration(train)

    print("=" * 72)
    print("PHASE 9 — RETURN FORECAST EMPIRICAL BENCHMARK")
    print("=" * 72)
    print(f"Observations with return target: {len(merged)}")
    print(
        f"Partitions: fit={len(fit)}, calibration={len(calibration)}, "
        f"validation={len(validation)}, test={len(test)}"
    )
    print(f"Features: {len(feature_columns)}")
    print(f"Boundaries: {boundaries}")

    results = {
        "protocol": {
            "train_ratio": 0.70,
            "validation_ratio": 0.15,
            "test_ratio": 0.15,
            "purge_minutes": 60,
            "calibration_ratio_within_train": 0.10,
            "calibration_confidence": args.confidence,
            "target_column": "future_return",
            "target_definition": (
                "close-to-close return from decision timestamp to the "
                "12th strictly-future 5-minute candle unless target artifact "
                "was built with another horizon"
            ),
            "external_test_used_for_model_selection": False,
        },
        "source": {
            "dataset": str(Path(args.dataset)),
            "targets": str(Path(args.targets)),
            "feature_count": len(feature_columns),
            "feature_columns": feature_columns,
        },
        "counts": {
            "merged": len(merged),
            "fit": len(fit),
            "calibration": len(calibration),
            "validation": len(validation),
            "test": len(test),
        },
        "boundaries": boundaries,
        "models": {},
    }

    for family in ("ridge", "random_forest"):
        print(f"\n--- {family} ---")
        model_result = _run_model(
            family=family,
            fit=fit,
            calibration=calibration,
            validation=validation,
            test=test,
            feature_columns=feature_columns,
            confidence=args.confidence,
        )
        results["models"][family] = model_result
        for partition in ("validation", "test"):
            point = model_result[partition]["point_forecast"]
            interval = model_result[partition]["interval"]
            print(
                f"{partition}: MAE={point['mae']:.8f} "
                f"RMSE={point['rmse']:.8f} "
                f"directional_accuracy={point['directional_accuracy']:.4f} "
                f"coverage={interval['empirical_coverage']:.4f}"
            )

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"\nBenchmark written to: {args.out}")


if __name__ == "__main__":
    main()
