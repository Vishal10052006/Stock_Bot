"""Empirical walk-forward benchmark for the fixed-weight return ensemble.

The ensemble weights are explicit configuration and are not learned from the
final OOS partition. This benchmark reuses the purged expanding walk-forward
protocol, trains the two pre-declared baseline components independently, and
evaluates their fixed 50/50 point forecast and conservative interval envelope.

This is validation evidence only. It does not select production weights and
does not authorize trades.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

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
from scripts.run_phase9_return_forecast_walk_forward import (  # noqa: E402
    _prepare_features,
    _split_train_for_calibration,
)


def _load_merged(dataset_path: Path, target_path: Path) -> tuple[pd.DataFrame, list[str], int]:
    dataset = pd.read_parquet(dataset_path)
    targets = pd.read_parquet(target_path)
    dataset["timestamp"] = pd.to_datetime(dataset["timestamp"], errors="raise")
    targets["timestamp"] = pd.to_datetime(targets["timestamp"], errors="raise")

    if not isinstance(dataset["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("dataset timestamps must be timezone-aware")
    if not isinstance(targets["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("target timestamps must be timezone-aware")

    required = {"timestamp", "symbol", "future_timestamp", "future_return", "horizon_bars"}
    missing = required.difference(targets.columns)
    if missing:
        raise ValueError(f"targets missing required columns: {sorted(missing)}")

    horizons = targets["horizon_bars"].dropna().astype(int).unique()
    if len(horizons) != 1 or int(horizons[0]) < 1:
        raise ValueError("target artifact must contain exactly one positive horizon")

    feature_columns = [column for column in FEATURE_COLUMNS if column in dataset.columns]
    if not feature_columns:
        raise ValueError("No canonical Phase 5 feature columns are present")

    merged = dataset.merge(
        targets[["timestamp", "symbol", "future_timestamp", "future_return", "horizon_bars"]],
        on=["timestamp", "symbol"],
        how="inner",
        validate="one_to_one",
    )
    if merged.empty:
        raise ValueError("No feature/return-target observations overlap")

    merged["future_timestamp"] = pd.to_datetime(merged["future_timestamp"], errors="raise")
    if not (merged["future_timestamp"] > merged["timestamp"]).all():
        raise ValueError("Return target contains a non-future timestamp")

    return (
        merged.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True),
        feature_columns,
        int(horizons[0]),
    )


def _run_fold(
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_columns: list[str],
    weights: tuple[float, float],
    confidence: float,
) -> dict[str, object]:
    fit, calibration = _split_train_for_calibration(train)

    models = {}
    predictions = {}
    intervals = {}

    for family in ("ridge", "random_forest"):
        X_fit, [X_cal, X_test] = _prepare_features(
            fit,
            [calibration, test],
            feature_columns,
            scale=family == "ridge",
        )
        model = ReturnForecastModel(ReturnForecastConfig(model_family=family))
        model.fit(X_fit, fit["future_return"])
        model.calibrate(X_cal, calibration["future_return"], confidence=confidence)
        predictions[family] = model.predict(X_test)
        intervals[family] = model.predict_interval(X_test)
        models[family] = model

    ridge_weight, rf_weight = weights
    ensemble_prediction = (
        ridge_weight * predictions["ridge"]
        + rf_weight * predictions["random_forest"]
    )
    ensemble_lower = np.minimum(
        intervals["ridge"][0],
        intervals["random_forest"][0],
    )
    ensemble_upper = np.maximum(
        intervals["ridge"][1],
        intervals["random_forest"][1],
    )
    actual = test["future_return"].to_numpy(dtype=float)

    result = {
        "fit_rows": len(fit),
        "calibration_rows": len(calibration),
        "test_rows": len(test),
        "fit_end": fit["timestamp"].max().isoformat(),
        "calibration_start": calibration["timestamp"].min().isoformat(),
        "test_start": test["timestamp"].min().isoformat(),
        "components": {},
        "ensemble": {
            "point_forecast": evaluate_return_forecasts(actual, ensemble_prediction),
            "interval": evaluate_prediction_intervals(
                actual,
                ensemble_lower,
                ensemble_upper,
                confidence_level=confidence,
            ),
            "interval_method": "component_envelope",
        },
    }

    for family in ("ridge", "random_forest"):
        lower, upper = intervals[family]
        result["components"][family] = {
            "point_forecast": evaluate_return_forecasts(actual, predictions[family]),
            "interval": evaluate_prediction_intervals(
                actual,
                lower,
                upper,
                confidence_level=confidence,
            ),
        }

    return result


def _aggregate(folds: list[dict[str, object]]) -> dict[str, object]:
    if not folds:
        raise ValueError("at least one fold is required")
    total = sum(int(fold["test_rows"]) for fold in folds)

    def weighted(section: str, metric: str) -> float:
        return float(
            sum(
                float(fold[section]["point_forecast"][metric]) * int(fold["test_rows"])
                for fold in folds
            )
            / total
        )

    return {
        "test_rows": total,
        "ensemble": {
            "mae": weighted("ensemble", "mae"),
            "rmse": weighted("ensemble", "rmse"),
            "directional_accuracy": weighted("ensemble", "directional_accuracy"),
            "interval_coverage": float(
                sum(
                    float(fold["ensemble"]["interval"]["empirical_coverage"])
                    * int(fold["test_rows"])
                    for fold in folds
                )
                / total
            ),
        },
        "components": {
            family: {
                "mae": weighted_component(folds, family, "mae", total),
                "rmse": weighted_component(folds, family, "rmse", total),
                "directional_accuracy": weighted_component(
                    folds, family, "directional_accuracy", total
                ),
                "interval_coverage": weighted_component_interval(
                    folds, family, total
                ),
            }
            for family in ("ridge", "random_forest")
        },
    }


def weighted_component(
    folds: list[dict[str, object]],
    family: str,
    metric: str,
    total: int,
) -> float:
    return float(
        sum(
            float(fold["components"][family]["point_forecast"][metric])
            * int(fold["test_rows"])
            for fold in folds
        )
        / total
    )


def weighted_component_interval(
    folds: list[dict[str, object]],
    family: str,
    total: int,
) -> float:
    return float(
        sum(
            float(fold["components"][family]["interval"]["empirical_coverage"])
            * int(fold["test_rows"])
            for fold in folds
        )
        / total
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--confidence", type=float, default=0.90)
    parser.add_argument("--ridge-weight", type=float, default=0.50)
    parser.add_argument("--random-forest-weight", type=float, default=0.50)
    args = parser.parse_args()

    if args.folds < 2:
        raise ValueError("--folds must be at least 2")
    if args.ridge_weight < 0 or args.random_forest_weight < 0:
        raise ValueError("ensemble weights must be non-negative")
    total_weight = args.ridge_weight + args.random_forest_weight
    if total_weight <= 0:
        raise ValueError("ensemble weights must have a positive sum")

    weights = (
        args.ridge_weight / total_weight,
        args.random_forest_weight / total_weight,
    )

    merged, feature_columns, horizon = _load_merged(
        Path(args.dataset),
        Path(args.targets),
    )

    windows = generate_windows(
        merged,
        folds=args.folds,
        train_ratio=0.60,
        test_ratio=0.40,
        purge_minutes=60,
    )

    print("=" * 72)
    print("PHASE 9 — FIXED-WEIGHT RETURN ENSEMBLE WALK-FORWARD")
    print("=" * 72)
    print(f"Observations: {len(merged)}")
    print(f"Folds: {len(windows)}")
    print(f"Features: {len(feature_columns)}")
    print(f"Target horizon bars: {horizon}")
    print(f"Weights: Ridge={weights[0]:.4f}, RandomForest={weights[1]:.4f}")

    fold_results = []
    for window in windows:
        timestamps = pd.to_datetime(merged["timestamp"], utc=True)
        train = merged.loc[timestamps <= window.train_end].copy()
        test = merged.loc[
            (timestamps >= window.test_start) & (timestamps <= window.test_end)
        ].copy()
        if train.empty or test.empty:
            raise RuntimeError(f"fold {window.fold_id} produced an empty partition")
        if train["timestamp"].max() >= test["timestamp"].min():
            raise RuntimeError(f"fold {window.fold_id} violates chronological separation")

        result = _run_fold(train, test, feature_columns, weights, args.confidence)
        result["fold_id"] = window.fold_id
        result["purged_rows"] = window.purged_rows
        fold_results.append(result)

        point = result["ensemble"]["point_forecast"]
        interval = result["ensemble"]["interval"]
        print(
            f"fold {window.fold_id}: train={len(train)} test={len(test)} "
            f"MAE={point['mae']:.8f} RMSE={point['rmse']:.8f} "
            f"direction={point['directional_accuracy']:.4f} "
            f"coverage={interval['empirical_coverage']:.4f}"
        )

    output = {
        "protocol": {
            "folds": args.folds,
            "train_ratio_per_window": 0.60,
            "test_ratio_per_window": 0.40,
            "purge_minutes": 60,
            "calibration_ratio_within_train": 0.10,
            "confidence": args.confidence,
            "weights": {
                "ridge": weights[0],
                "random_forest": weights[1],
            },
            "weights_learned_from_final_oos": False,
            "final_oos_used": False,
        },
        "source": {
            "dataset": str(Path(args.dataset)),
            "targets": str(Path(args.targets)),
            "feature_count": len(feature_columns),
            "horizon_bars": horizon,
        },
        "folds": fold_results,
        "aggregate": _aggregate(fold_results),
    }

    Path(args.out).write_text(json.dumps(output, indent=2))
    print(f"\nEnsemble walk-forward artifact: {args.out}")


if __name__ == "__main__":
    main()
