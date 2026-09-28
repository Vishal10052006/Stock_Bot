"""Run a purged expanding walk-forward return-forecast benchmark.

Each fold:
  - trains only on observations before the future test block;
  - reserves the latest 10% of that fold's training observations for
    chronological conformal calibration;
  - fits preprocessing on the earlier fit partition only;
  - evaluates the future test block once;
  - never uses a later fold to tune an earlier fold.

This is empirical validation infrastructure. It does not select a production
model and does not authorize trades.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtesting.walk_forward import generate_windows  # noqa: E402
from market.features.builder import FEATURE_COLUMNS  # noqa: E402
from ml.evaluation.return_forecast import (  # noqa: E402
    evaluate_prediction_intervals,
    evaluate_return_forecasts,
)
from ml.models.return_forecast import (  # noqa: E402
    ReturnForecastConfig,
    ReturnForecastModel,
)


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
    if len(timestamps) < 3:
        raise ValueError("walk-forward training set needs at least 3 timestamps")

    split_index = max(1, int(len(timestamps) * (1.0 - calibration_ratio)))
    split_index = min(split_index, len(timestamps) - 1)
    boundary = timestamps.iloc[split_index - 1]

    fit = train.loc[train["timestamp"] <= boundary].copy()
    calibration = train.loc[train["timestamp"] > boundary].copy()
    if fit.empty or calibration.empty:
        raise ValueError("training/calibration split produced an empty partition")
    return fit, calibration


def _prepare_features(
    fit: pd.DataFrame,
    frames: list[pd.DataFrame],
    feature_columns: list[str],
    *,
    scale: bool,
) -> tuple[np.ndarray, list[np.ndarray]]:
    imputer = SimpleImputer(strategy="median")
    X_fit = imputer.fit_transform(fit[feature_columns])
    transformed = [imputer.transform(frame[feature_columns]) for frame in frames]

    if scale:
        scaler = StandardScaler()
        X_fit = scaler.fit_transform(X_fit)
        transformed = [scaler.transform(values) for values in transformed]

    return X_fit, transformed


def _run_fold(
    *,
    family: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_columns: list[str],
    confidence: float,
) -> dict[str, object]:
    fit, calibration = _split_train_for_calibration(train)
    X_fit, [X_cal, X_test] = _prepare_features(
        fit,
        [calibration, test],
        feature_columns,
        scale=family == "ridge",
    )

    model = ReturnForecastModel(ReturnForecastConfig(model_family=family))
    model.fit(X_fit, fit["future_return"])
    model.calibrate(
        X_cal,
        calibration["future_return"],
        confidence=confidence,
    )

    predicted = model.predict(X_test)
    lower, upper = model.predict_interval(X_test)
    actual = test["future_return"].to_numpy(dtype=float)

    point = evaluate_return_forecasts(actual, predicted)
    interval = evaluate_prediction_intervals(
        actual,
        lower,
        upper,
        confidence_level=confidence,
    )

    zero_baseline = np.zeros_like(actual)
    baseline = evaluate_return_forecasts(actual, zero_baseline)

    return {
        "fit_rows": len(fit),
        "calibration_rows": len(calibration),
        "test_rows": len(test),
        "fit_end": fit["timestamp"].max().isoformat(),
        "calibration_start": calibration["timestamp"].min().isoformat(),
        "calibration_end": calibration["timestamp"].max().isoformat(),
        "test_start": test["timestamp"].min().isoformat(),
        "test_end": test["timestamp"].max().isoformat(),
        "conformal_radius": model.conformal_radius,
        "point_forecast": point,
        "interval": interval,
        "zero_return_baseline": baseline,
    }


def _aggregate_fold_metrics(
    folds: list[dict[str, object]],
) -> dict[str, object]:
    if not folds:
        raise ValueError("at least one fold is required")

    total = sum(int(fold["test_rows"]) for fold in folds)
    weighted = {}
    for metric in (
        "mae",
        "rmse",
        "mean_error",
        "directional_accuracy",
    ):
        weighted[metric] = float(
            sum(
                float(fold["point_forecast"][metric]) * int(fold["test_rows"])
                for fold in folds
            )
            / total
        )

    coverage = float(
        sum(
            float(fold["interval"]["empirical_coverage"])
            * int(fold["test_rows"])
            for fold in folds
        )
        / total
    )
    baseline = float(
        sum(
            float(fold["zero_return_baseline"]["mae"]) * int(fold["test_rows"])
            for fold in folds
        )
        / total
    )

    return {
        "test_rows": total,
        "weighted_mean": weighted,
        "weighted_interval_coverage": coverage,
        "weighted_zero_return_baseline_mae": baseline,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--train-ratio", type=float, default=0.60)
    parser.add_argument("--confidence", type=float, default=0.90)
    parser.add_argument("--purge-minutes", type=int, default=60)
    args = parser.parse_args()

    if args.folds < 2:
        raise ValueError("--folds must be at least 2")

    dataset = pd.read_parquet(args.dataset)
    targets = pd.read_parquet(args.targets)
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
        raise ValueError("No canonical Phase 5 feature columns are present.")

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
        raise ValueError("No feature/return-target observations overlap.")

    merged["future_timestamp"] = pd.to_datetime(
        merged["future_timestamp"], errors="raise"
    )
    if not (merged["future_timestamp"] > merged["timestamp"]).all():
        raise ValueError("Return target contains a non-future timestamp.")

    merged = merged.sort_values(["timestamp", "symbol"], kind="stable").reset_index(
        drop=True
    )

    windows = generate_windows(
        merged,
        folds=args.folds,
        train_ratio=args.train_ratio,
        test_ratio=1.0 - args.train_ratio,
        purge_minutes=args.purge_minutes,
    )

    print("=" * 72)
    print("PHASE 9 — RETURN FORECAST PURGED WALK-FORWARD")
    print("=" * 72)
    print(f"Observations: {len(merged)}")
    print(f"Folds: {len(windows)}")
    print(f"Features: {len(feature_columns)}")
    print(f"Target horizon bars: {int(horizons[0])}")

    results: dict[str, object] = {
        "protocol": {
            "folds": args.folds,
            "initial_train_ratio": args.train_ratio,
            "calibration_ratio_within_each_train": 0.10,
            "purge_minutes": args.purge_minutes,
            "confidence": args.confidence,
            "external_future_test_used_for_model_selection": False,
        },
        "source": {
            "dataset": str(Path(args.dataset)),
            "targets": str(Path(args.targets)),
            "feature_count": len(feature_columns),
            "feature_columns": feature_columns,
            "horizon_bars": int(horizons[0]),
        },
        "models": {},
    }

    for family in ("ridge", "random_forest"):
        print(f"\n--- {family} ---")
        fold_results: list[dict[str, object]] = []

        for window in windows:
            timestamps = pd.to_datetime(merged["timestamp"], utc=True)
            train_mask = timestamps <= window.train_end
            test_mask = (
                (timestamps >= window.test_start)
                & (timestamps <= window.test_end)
            )
            train = merged.loc[train_mask].copy()
            test = merged.loc[test_mask].copy()

            if train.empty or test.empty:
                raise RuntimeError(f"fold {window.fold_id} produced an empty partition")
            if train["timestamp"].max() >= test["timestamp"].min():
                raise RuntimeError(
                    f"fold {window.fold_id} violates chronological separation"
                )

            result = _run_fold(
                family=family,
                train=train,
                test=test,
                feature_columns=feature_columns,
                confidence=args.confidence,
            )
            result["fold_id"] = window.fold_id
            result["purged_rows"] = window.purged_rows
            fold_results.append(result)

            point = result["point_forecast"]
            interval = result["interval"]
            print(
                f"fold {window.fold_id}: train={len(train)} "
                f"fit={result['fit_rows']} cal={result['calibration_rows']} "
                f"test={len(test)} MAE={point['mae']:.8f} "
                f"RMSE={point['rmse']:.8f} "
                f"direction={point['directional_accuracy']:.4f} "
                f"coverage={interval['empirical_coverage']:.4f}"
            )

        results["models"][family] = {
            "folds": fold_results,
            "aggregate": _aggregate_fold_metrics(fold_results),
        }

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"\nWalk-forward benchmark written to: {args.out}")


if __name__ == "__main__":
    main()
