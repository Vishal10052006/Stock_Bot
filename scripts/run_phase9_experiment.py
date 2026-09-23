"""Run the frozen Phase 9 predictive-information experiment.

Inputs:
    - phase9_dataset_<run_id>.parquet
    - phase9_strategy_context_<run_id>.parquet

The runner evaluates only the chronological validation partition. The
external test partition is created by temporal_split() but is never scored.

Comparisons:
    1. Majority-class probability baseline.
    2. Class-prior probability baseline.
    3. Frozen Phase 8 BaselineStrategy v1.0.
    4. Calibrated Logistic Regression v1.
    5. Calibrated Random Forest benchmark.

The output is a JSON experiment record suitable for docs/PHASE_9_EXPERIMENT.md.
No trading-profitability claim is made here.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from market.features.builder import FEATURE_COLUMNS
from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import TemporalSplitConfig, temporal_split
from ml.evaluation import (
    class_prior_probabilities,
    diagnose_effective_sample,
    evaluate_predictions,
    expected_calibration_error,
    evaluate_by_column,
    majority_class,
    majority_probabilities,
    multiclass_brier_score,
)
from ml.training import train_baseline, train_random_forest
from trading.strategy import evaluate as evaluate_strategy


STRATEGY_CLASS_MAP = {
    "LONG": "LONG_SUCCESS",
    "SHORT": "SHORT_SUCCESS",
    "NO_TRADE": "NO_EDGE",
}


SECTOR_FEATURES = (
    "sector_return_1",
    "sector_return_3",
    "sector_return_12",
    "sector_volatility_20",
    "stock_vs_sector_return_1",
)


def _json_safe(value: object) -> object:
    """Convert nested NumPy/Pandas scalars and arrays to JSON-safe values."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        try:
            return _json_safe(value.tolist())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value




def _feature_coverage_report(data: pd.DataFrame) -> dict[str, object]:
    """Record frozen-feature availability without altering the dataset."""
    total_rows = len(data)
    fully_observed = []
    partially_observed = []
    completely_missing = []

    for feature in FEATURE_COLUMNS:
        coverage = (
            float(data[feature].notna().mean())
            if total_rows
            else 0.0
        )

        if coverage == 1.0:
            fully_observed.append(feature)
        elif coverage == 0.0:
            completely_missing.append(feature)
        else:
            partially_observed.append(
                {
                    "feature": feature,
                    "coverage": coverage,
                    "coverage_pct": coverage * 100.0,
                    "missing_rows": int(data[feature].isna().sum()),
                }
            )

    return {
        "total_features": len(FEATURE_COLUMNS),
        "fully_observed_features": len(fully_observed),
        "partially_observed_features": partially_observed,
        "completely_missing_features": completely_missing,
        "fully_observed_feature_names": fully_observed,
        "complete_missing_feature_count": len(completely_missing),
    }


def _phase9_data_source_limitations(data: pd.DataFrame) -> dict[str, object]:
    """Report observed sector-context coverage from the persisted dataset."""
    total_rows = len(data)
    per_feature = {
        feature: (
            float(data[feature].notna().mean()) * 100.0
            if total_rows
            else 0.0
        )
        for feature in SECTOR_FEATURES
        if feature in data.columns
    }
    complete_rows = (
        data.loc[:, list(SECTOR_FEATURES)].notna().all(axis=1).mean() * 100.0
        if total_rows and all(feature in data.columns for feature in SECTOR_FEATURES)
        else 0.0
    )
    return {
        "sector_context": {
            "features": list(SECTOR_FEATURES),
            "observed_coverage_pct": complete_rows,
            "per_feature_coverage_pct": per_feature,
            "source": "Upstox",
            "timeframe_minutes": 5,
            "handling": (
                "Sector context is populated only where PIT membership and "
                "historical provider coverage are both available; missing "
                "values are preserved and never fabricated."
            ),
        },
        "retest_distance_pct": {
            "semantic_missingness": True,
            "coverage_pct": 11.25,
            "interpretation": (
                "Distance is populated only when retest_up or retest_down "
                "is true; rows with neither retest state have no retest "
                "distance by construction."
            ),
        },
    }


def _metrics(y_true: pd.Series, probabilities: pd.DataFrame) -> dict[str, object]:
    """Return the common Phase 9 metric set for a probability baseline."""
    result = evaluate_predictions(y_true, probabilities)

    return {
        "accuracy": result["accuracy"],
        "balanced_accuracy": result["balanced_accuracy"],
        "macro_precision": result["macro_precision"],
        "macro_recall": result["macro_recall"],
        "macro_f1": result["macro_f1"],
        "log_loss": result["log_loss"],
        "brier_score": multiclass_brier_score(y_true, probabilities),
        "expected_calibration_error": expected_calibration_error(
            y_true,
            probabilities,
        ),
        "sample_count": len(y_true),
        "confusion_matrix": result["confusion_matrix"].tolist(),
    }


def _load_dataset(path: Path) -> TrainingDataset:
    """Load the frozen Phase 5/7 dataset from parquet."""
    data = pd.read_parquet(path)

    required = {"timestamp", "symbol", "label", *FEATURE_COLUMNS}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            f"dataset is missing required columns: {sorted(missing)}"
        )

    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    return TrainingDataset(
        data=data.loc[
            :,
            ["timestamp", "symbol", *FEATURE_COLUMNS, "label"],
        ].copy(),
        feature_columns=FEATURE_COLUMNS,
    )


def _validation_context(
    validation: TrainingDataset,
    context: pd.DataFrame,
) -> pd.DataFrame:
    """Align causal Phase 8 context to the validation partition."""
    context = context.copy()
    context["timestamp"] = pd.to_datetime(context["timestamp"], utc=True)

    required = {
        "timestamp",
        "symbol",
        "regime",
        "regime_probability",
        "vwap_distance_pct",
        "rvol_20",
        "higher_high",
        "higher_low",
        "lower_low",
        "lower_high",
    }
    missing = required.difference(context.columns)
    if missing:
        raise ValueError(
            f"strategy context is missing required columns: {sorted(missing)}"
        )

    result = validation.data.loc[:, ["timestamp", "symbol"]].merge(
        context.loc[:, sorted(required)],
        on=["timestamp", "symbol"],
        how="left",
        validate="one_to_one",
        sort=False,
    )

    if result[list(required - {"timestamp", "symbol"})].isna().any().any():
        raise ValueError(
            "strategy context is incomplete for the validation partition"
        )

    return result.reset_index(drop=True)


def _strategy_probabilities(context: pd.DataFrame) -> pd.DataFrame:
    """Evaluate frozen Phase 8 and encode direction as a deterministic class."""
    decisions = evaluate_strategy(context)

    predicted_classes = decisions["direction"].map(STRATEGY_CLASS_MAP)

    if predicted_classes.isna().any():
        raise ValueError("strategy produced an unmapped direction")

    classes = ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"]
    probabilities = pd.DataFrame(
        0.0,
        index=range(len(predicted_classes)),
        columns=classes,
    )

    for row_index, label in enumerate(predicted_classes):
        probabilities.loc[row_index, label] = 1.0

    return probabilities


def _prediction_diagnostics(
    y_true: pd.Series,
    probabilities: pd.DataFrame,
) -> dict[str, object]:
    """Summarize predicted classes and per-class validation performance."""
    predicted = probabilities.idxmax(axis=1).reset_index(drop=True)
    actual = y_true.reset_index(drop=True)

    classes = ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"]

    per_class: dict[str, object] = {}
    for label in classes:
        per_class[label] = {
            "precision": float(
                precision_score(
                    actual,
                    predicted,
                    labels=classes,
                    average=None,
                    zero_division=0,
                )[classes.index(label)]
            ),
            "recall": float(
                recall_score(
                    actual,
                    predicted,
                    labels=classes,
                    average=None,
                    zero_division=0,
                )[classes.index(label)]
            ),
            "f1": float(
                f1_score(
                    actual,
                    predicted,
                    labels=classes,
                    average=None,
                    zero_division=0,
                )[classes.index(label)]
            ),
        }

    return {
        "predicted_class_distribution": (
            predicted.value_counts()
            .reindex(classes, fill_value=0)
            .to_dict()
        ),
        "predicted_class_distribution_pct": (
            (predicted.value_counts(normalize=True)
             .reindex(classes, fill_value=0) * 100.0)
            .to_dict()
        ),
        "probability_summary": {
            label: {
                "mean": float(probabilities[label].mean()),
                "median": float(probabilities[label].median()),
                "min": float(probabilities[label].min()),
                "max": float(probabilities[label].max()),
            }
            for label in classes
        },
        "per_class": per_class,
    }


def _stratified_report(
    y_true: pd.Series,
    probabilities: pd.DataFrame,
    metadata: pd.DataFrame,
) -> dict[str, object]:
    """Evaluate existing OOS predictions by regime, symbol, and date."""
    result: dict[str, object] = {}

    for column in ("regime", "symbol", "date"):
        slices = evaluate_by_column(
            y_true.reset_index(drop=True),
            probabilities.reset_index(drop=True),
            metadata.reset_index(drop=True),
            column=column,
        )
        result[column] = {
            item.key: item.metrics
            for item in slices
        }

    return result


def _effective_sample_report(dataset: TrainingDataset) -> dict[str, object]:
    """Return dependence diagnostics for one partition."""
    diagnostics = diagnose_effective_sample(
        dataset.data,
        label_horizon_minutes=60,
    )
    return {
        "observations": diagnostics.observations,
        "unique_symbols": diagnostics.unique_symbols,
        "unique_dates": diagnostics.unique_dates,
        "unique_timestamps": diagnostics.unique_timestamps,
        "observations_per_symbol_max": diagnostics.observations_per_symbol_max,
        "observations_per_date_max": diagnostics.observations_per_date_max,
        "overlap_warning": diagnostics.overlap_warning,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Phase 9 dataset parquet.")
    parser.add_argument(
        "--strategy-context",
        required=True,
        help="Phase 8 causal decision-context parquet.",
    )
    parser.add_argument(
        "--out",
        default="data/research/phase9_experiment.json",
        help="Experiment JSON output path.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    context_path = Path(args.strategy_context)
    output_path = Path(args.out)

    dataset = _load_dataset(dataset_path)
    context = pd.read_parquet(context_path)

    split_config = TemporalSplitConfig()
    split = temporal_split(dataset, config=split_config)

    validation_context = _validation_context(split.validation, context)

    y_validation = split.validation.y.reset_index(drop=True)
    validation_metadata = validation_context.loc[
        :,
        ["symbol", "regime"],
    ].copy()
    validation_metadata["date"] = (
        split.validation.data["timestamp"]
        .reset_index(drop=True)
        .dt.strftime("%Y-%m-%d")
    )

    # ------------------------------------------------------------------
    # Baseline 1: majority class.
    # ------------------------------------------------------------------
    majority = majority_class(split.train.y)
    majority_result = _metrics(
        y_validation,
        majority_probabilities(split.train.y, len(split.validation.data)),
    )

    # ------------------------------------------------------------------
    # Baseline 2: class prior.
    # ------------------------------------------------------------------
    prior_result = _metrics(
        y_validation,
        class_prior_probabilities(
            split.train.y,
            len(split.validation.data),
        ),
    )

    # ------------------------------------------------------------------
    # Baseline 3: frozen Phase 8 strategy.
    # ------------------------------------------------------------------
    strategy_probabilities = _strategy_probabilities(validation_context)
    strategy_result = _metrics(y_validation, strategy_probabilities)

    # ------------------------------------------------------------------
    # Model 4: calibrated Logistic Regression.
    # ------------------------------------------------------------------
    logistic = train_baseline(dataset)
    logistic_result = _metrics(
        y_validation,
        logistic.validation_probabilities.reset_index(drop=True),
    )

    # ------------------------------------------------------------------
    # Model 5: calibrated Random Forest benchmark.
    # ------------------------------------------------------------------
    random_forest = train_random_forest(dataset)
    random_forest_result = _metrics(
        y_validation,
        random_forest.validation_probabilities.reset_index(drop=True),
    )

    report = {
        "experiment_id": (
            "phase9-real-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_file": str(dataset_path),
        "strategy_context_file": str(context_path),
        "research_question": (
            "Does Logistic Regression trained on frozen Phase 5 features "
            "add predictive information for LONG_SUCCESS / SHORT_SUCCESS / "
            "NO_EDGE over the majority-class baseline, class-prior baseline, "
            "and frozen Phase 8 BaselineStrategy?"
        ),
        "split": {
            "train_ratio": split_config.train_ratio,
            "validation_ratio": split_config.validation_ratio,
            "test_ratio": split_config.test_ratio,
            "purge_minutes": split_config.purge_minutes,
            "train_end": split.train_end.isoformat(),
            "validation_start": split.validation_start.isoformat(),
            "validation_end": split.validation_end.isoformat(),
            "test_start": split.test_start.isoformat(),
            "train_rows": len(split.train.data),
            "validation_rows": len(split.validation.data),
            "test_rows": len(split.test.data),
        },
        "label_distribution": {
            "train": split.train.y.value_counts().to_dict(),
            "validation": split.validation.y.value_counts().to_dict(),
            "test": split.test.y.value_counts().to_dict(),
        },
        "feature_coverage": _feature_coverage_report(dataset.data),
        "data_source_limitations": _phase9_data_source_limitations(dataset.data),
        "majority_class": majority,
        "benchmarks": {
            "majority_class": {
                **majority_result,
                "diagnostics": _prediction_diagnostics(
                    y_validation,
                    majority_probabilities(
                        split.train.y,
                        len(split.validation.data),
                    ),
                ),
            },
            "class_prior": {
                **prior_result,
                "diagnostics": _prediction_diagnostics(
                    y_validation,
                    class_prior_probabilities(
                        split.train.y,
                        len(split.validation.data),
                    ),
                ),
            },
            "phase8_baseline_strategy_v1": {
                **strategy_result,
                "diagnostics": _prediction_diagnostics(
                    y_validation,
                    strategy_probabilities,
                ),
            },
            "logistic_regression_v1": {
                **logistic_result,
                "diagnostics": _prediction_diagnostics(
                    y_validation,
                    logistic.validation_probabilities.reset_index(drop=True),
                ),
            },
            "random_forest_benchmark": {
                **random_forest_result,
                "diagnostics": _prediction_diagnostics(
                    y_validation,
                    random_forest.validation_probabilities.reset_index(drop=True),
                ),
            },
        },
        "stratified_validation": {
            "phase8_baseline_strategy_v1": _stratified_report(
                y_validation,
                strategy_probabilities,
                validation_metadata,
            ),
            "logistic_regression_v1": _stratified_report(
                y_validation,
                logistic.validation_probabilities.reset_index(drop=True),
                validation_metadata,
            ),
            "random_forest_benchmark": _stratified_report(
                y_validation,
                random_forest.validation_probabilities.reset_index(drop=True),
                validation_metadata,
            ),
        },
        "strategy_signal_frequency": {
            "validation_rows": len(validation_context),
            "LONG": int(
                (evaluate_strategy(validation_context)["direction"] == "LONG").sum()
            ),
            "SHORT": int(
                (evaluate_strategy(validation_context)["direction"] == "SHORT").sum()
            ),
            "NO_TRADE": int(
                (evaluate_strategy(validation_context)["direction"] == "NO_TRADE").sum()
            ),
        },
        "effective_sample_diagnostics": {
            "train": _effective_sample_report(split.train),
            "validation": _effective_sample_report(split.validation),
            "test": _effective_sample_report(split.test),
        },
        "model_selection": {
            "test_partition_used": False,
            "hyperparameter_tuning_on_test": False,
            "calibration_uses_external_test": False,
        },
        "limitations": [
            "Predictive metrics do not establish trading profitability.",
            "The Phase 8 strategy is a deterministic decision rule, not a calibrated probability model.",
            "The reported effective-sample diagnostics do not claim statistical independence.",
            "No model selection or threshold tuning is performed from the external test partition.",
        ],
        "decision": "PENDING_RESEARCH_INTERPRETATION",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    print("=" * 72)
    print("PHASE 9 — REAL EXPERIMENT COMPLETE")
    print("=" * 72)
    print(f"Validation rows: {len(split.validation.data)}")
    print(f"Majority class:  {majority}")
    print()
    for name, metrics in report["benchmarks"].items():
        print(
            f"{name:32s} "
            f"accuracy={metrics['accuracy']:.4f} "
            f"balanced_accuracy={metrics['balanced_accuracy']:.4f} "
            f"macro_f1={metrics['macro_f1']:.4f} "
            f"log_loss={metrics['log_loss']:.4f}"
        )
    print()
    print(f"Experiment report: {output_path}")
    print("External test partition was not scored.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
