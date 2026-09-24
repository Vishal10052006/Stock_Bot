"""Run the TimesFM 2.5 zero-shot causal walk-forward return experiment.

This experiment is prediction-only. It evaluates a pretrained price-forecasting
foundation model by converting its horizon endpoint forecast into the same
close-to-close return target used by the existing Phase 9 baselines.

Important:
- no model fitting/fine-tuning occurs;
- only observations strictly before each decision timestamp form context;
- context is session-local so overnight gaps are never treated as 5-minute bars;
- only walk-forward test folds are used;
- the locked final OOS partition is never used by this script;
- no trading decision is emitted.

The experiment is deliberately separate from the production-facing baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

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
from ml.models.foundation_forecast import (  # noqa: E402
    FoundationForecastConfig,
    FoundationForecastModel,
)

FROZEN_FOLDS = 3
FROZEN_TRAIN_RATIO = 0.60
FROZEN_PURGE_MINUTES = 60
FROZEN_CONFIDENCE = 0.80
FROZEN_CONTEXT_LENGTH = 64
FROZEN_HORIZON_BARS = 12
MIN_CONTEXT_POINTS = 32
BATCH_SIZE = 16


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_merged(
    dataset_path: Path,
    target_path: Path,
) -> tuple[pd.DataFrame, list[str], int]:
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
        "close",
        "future_timestamp",
        "future_return",
        "horizon_bars",
    }
    missing = required.difference(dataset.columns.union(targets.columns))
    if missing:
        raise ValueError(f"inputs missing required columns: {sorted(missing)}")

    horizons = targets["horizon_bars"].dropna().astype(int).unique()
    if len(horizons) != 1 or int(horizons[0]) != FROZEN_HORIZON_BARS:
        raise ValueError(
            f"target artifact must contain exactly horizon_bars={FROZEN_HORIZON_BARS}"
        )

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

    if not np.isfinite(merged["close"].to_numpy(dtype=float)).all():
        raise ValueError("close contains non-finite values")
    if (merged["close"] <= 0).any():
        raise ValueError("close must be strictly positive")

    merged = merged.sort_values(
        ["symbol", "timestamp"], kind="stable"
    ).reset_index(drop=True)
    return merged, feature_columns, int(horizons[0])


def _session_history(
    history: pd.DataFrame,
    *,
    symbol: str,
    timestamp: pd.Timestamp,
    context_length: int,
) -> np.ndarray | None:
    """Return strictly-past same-session closes for one decision timestamp."""
    symbol_rows = history.loc[
        (history["symbol"] == symbol)
        & (history["timestamp"] < timestamp)
        & (history["timestamp"].dt.date == timestamp.date())
    ].sort_values("timestamp")

    if len(symbol_rows) < MIN_CONTEXT_POINTS:
        return None

    values = symbol_rows["close"].to_numpy(dtype=np.float32)
    return values[-context_length:]


def _forecast_rows(
    model: FoundationForecastModel,
    *,
    history: pd.DataFrame,
    test: pd.DataFrame,
    context_length: int,
    horizon: int,
) -> tuple[pd.DataFrame, int]:
    rows: list[dict[str, object]] = []
    skipped = 0

    eligible: list[tuple[int, pd.Series, np.ndarray]] = []
    for row_index, row in test.iterrows():
        context = _session_history(
            history,
            symbol=str(row["symbol"]),
            timestamp=row["timestamp"],
            context_length=context_length,
        )
        if context is None:
            skipped += 1
            continue
        eligible.append((row_index, row, context))

    for start in range(0, len(eligible), BATCH_SIZE):
        batch = eligible[start : start + BATCH_SIZE]
        inputs = [item[2] for item in batch]
        point, quantiles = model.forecast(inputs, horizon=horizon)

        for offset, (_, row, context) in enumerate(batch):
            last_close = float(context[-1])
            predicted_price = float(point[offset, horizon - 1])
            lower_price = float(quantiles[offset, horizon - 1, 1])
            upper_price = float(quantiles[offset, horizon - 1, 9])

            predicted_return = predicted_price / last_close - 1.0
            lower_return = lower_price / last_close - 1.0
            upper_return = upper_price / last_close - 1.0

            if lower_return > upper_return:
                raise RuntimeError("foundation interval bounds crossed")

            rows.append(
                {
                    "timestamp": row["timestamp"].isoformat(),
                    "symbol": str(row["symbol"]),
                    "actual_return": float(row["future_return"]),
                    "predicted_return": predicted_return,
                    "lower_return": lower_return,
                    "upper_return": upper_return,
                    "context_points": int(len(context)),
                    "last_close": last_close,
                    "forecast_price": predicted_price,
                    "forecast_lower_price": lower_price,
                    "forecast_upper_price": upper_price,
                }
            )

    return pd.DataFrame(rows), skipped


def _evaluate(frame: pd.DataFrame) -> dict[str, object]:
    actual = frame["actual_return"].to_numpy(dtype=float)
    predicted = frame["predicted_return"].to_numpy(dtype=float)
    lower = frame["lower_return"].to_numpy(dtype=float)
    upper = frame["upper_return"].to_numpy(dtype=float)

    return {
        "point_forecast": evaluate_return_forecasts(actual, predicted),
        "interval": evaluate_prediction_intervals(
            actual,
            lower,
            upper,
            confidence_level=FROZEN_CONFIDENCE,
        ),
        "zero_return_baseline": evaluate_return_forecasts(
            actual,
            np.zeros_like(actual),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    target_path = Path(args.targets)
    out_path = Path(args.out)

    merged, feature_columns, horizon = _load_merged(dataset_path, target_path)

    windows = generate_windows(
        merged,
        folds=FROZEN_FOLDS,
        train_ratio=FROZEN_TRAIN_RATIO,
        test_ratio=1.0 - FROZEN_TRAIN_RATIO,
        purge_minutes=FROZEN_PURGE_MINUTES,
    )

    config = FoundationForecastConfig(
        context_length=FROZEN_CONTEXT_LENGTH,
        max_horizon=FROZEN_HORIZON_BARS,
        batch_size=BATCH_SIZE,
    )

    print("=" * 72)
    print("PHASE 9 — TIMESFM 2.5 ZERO-SHOT WALK-FORWARD")
    print("=" * 72)
    print(f"Observations: {len(merged)}")
    print(f"Folds: {len(windows)}")
    print(f"Target horizon: {horizon} bars")
    print(f"Session-local context: {FROZEN_CONTEXT_LENGTH} bars")
    print(f"Minimum usable context: {MIN_CONTEXT_POINTS} bars")
    print(f"Confidence interval: {FROZEN_CONFIDENCE:.0%}")
    print("Final OOS: NOT USED")
    print("\nLoading TimesFM checkpoint once...")
    model = FoundationForecastModel(config).load()
    print(f"Model loaded: {model.is_loaded}")

    results: dict[str, object] = {
        "status": "FOUNDATION_WALK_FORWARD_EVIDENCE",
        "model": {
            "backend": config.backend,
            "model_id": config.model_id,
            "timesfm_package_version": importlib.metadata.version("timesfm"),
            "model_license_recorded_as": "Apache-2.0",
            "source_model_card": (
                "https://huggingface.co/google/timesfm-2.5-200m-pytorch"
            ),
            "config": {
                "context_length": config.context_length,
                "max_horizon": config.max_horizon,
                "batch_size": config.batch_size,
                "quantile_lower_index": config.quantile_lower_index,
                "quantile_median_index": config.quantile_median_index,
                "quantile_upper_index": config.quantile_upper_index,
            },
        },
        "protocol": {
            "folds": FROZEN_FOLDS,
            "train_ratio": FROZEN_TRAIN_RATIO,
            "purge_minutes": FROZEN_PURGE_MINUTES,
            "horizon_bars": horizon,
            "context_policy": (
                "last strictly-past closes from the same trading session only"
            ),
            "minimum_context_points": MIN_CONTEXT_POINTS,
            "confidence": FROZEN_CONFIDENCE,
            "fine_tuning": False,
            "model_selection_on_final_oos": False,
            "final_oos_used": False,
            "trading_decision_emitted": False,
        },
        "source": {
            "dataset": str(dataset_path),
            "dataset_sha256": _sha256_file(dataset_path),
            "targets": str(target_path),
            "targets_sha256": _sha256_file(target_path),
            "feature_count": len(feature_columns),
            "feature_columns": feature_columns,
        },
        "folds": [],
    }

    for window in windows:
        timestamps = pd.to_datetime(merged["timestamp"], utc=True)
        train = merged.loc[timestamps <= window.train_end].copy()
        test = merged.loc[
            (timestamps >= window.test_start)
            & (timestamps <= window.test_end)
        ].copy()

        if train.empty or test.empty:
            raise RuntimeError(f"fold {window.fold_id} produced an empty partition")
        if train["timestamp"].max() >= test["timestamp"].min():
            raise RuntimeError(
                f"fold {window.fold_id} violates chronological separation"
            )

        predictions, skipped = _forecast_rows(
            model,
            history=train,
            test=test,
            context_length=config.context_length,
            horizon=horizon,
        )

        if predictions.empty:
            raise RuntimeError(
                f"fold {window.fold_id} has no observations with sufficient "
                "session-local context"
            )

        metrics = _evaluate(predictions)
        fold_result = {
            "fold_id": window.fold_id,
            "train_rows": len(train),
            "test_rows": len(test),
            "evaluated_rows": len(predictions),
            "skipped_insufficient_context": skipped,
            "purged_rows": window.purged_rows,
            "train_end": train["timestamp"].max().isoformat(),
            "test_start": test["timestamp"].min().isoformat(),
            "test_end": test["timestamp"].max().isoformat(),
            **metrics,
        }
        results["folds"].append(fold_result)

        point = metrics["point_forecast"]
        interval = metrics["interval"]
        print(
            f"fold {window.fold_id}: train={len(train)} test={len(test)} "
            f"evaluated={len(predictions)} skipped={skipped} "
            f"MAE={point['mae']:.8f} RMSE={point['rmse']:.8f} "
            f"direction={point['directional_accuracy']:.4f} "
            f"coverage={interval['empirical_coverage']:.4f}"
        )

    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nFoundation experiment artifact: {out_path}")


if __name__ == "__main__":
    main()
