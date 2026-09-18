"""Train and evaluate the Phase 9 real-data model benchmarks.

This runner reuses the existing real-data smoke pipeline so the first
end-to-end model run cannot silently drift from the dataset construction
already verified in Phase 9.

The script evaluates:
    - calibrated Logistic Regression baseline
    - calibrated Random Forest benchmark

Only validation probabilities are evaluated. The test partition remains
untouched.
"""

from __future__ import annotations

import runpy
from pathlib import Path

from ml.evaluation import evaluate_training_result
from ml.training import train_baseline, train_random_forest


ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "scripts" / "phase9_real_data_smoke.py"


def _load_real_dataset():
    """Execute the verified real-data builder and return its result."""
    namespace = runpy.run_path(str(SMOKE_SCRIPT), run_name="__phase9_real_data__")
    result = namespace.get("result")

    if result is None:
        raise RuntimeError(
            "phase9_real_data_smoke.py did not expose its Phase9DatasetResult "
            "as global 'result'."
        )

    if not hasattr(result, "training_dataset"):
        raise TypeError("real-data smoke result is not a Phase9DatasetResult.")

    return result


def _print_result(name: str, training_result, validation_dataset) -> None:
    """Print reproducible Phase 9 validation metrics."""
    evaluation = evaluate_training_result(
        training_result,
        validation_dataset,
    )

    print()
    print("-" * 72)
    print(name)
    print("-" * 72)

    print(f"train_rows       = {training_result.train_rows}")
    print(f"calibration_rows = {training_result.calibration_rows}")
    print(f"validation_rows  = {training_result.validation_rows}")
    print(f"test_rows        = {training_result.test_rows}")

    print(f"accuracy         = {evaluation.accuracy:.6f}")
    print(f"balanced_accuracy= {evaluation.balanced_accuracy:.6f}")
    print(f"macro_precision  = {evaluation.macro_precision:.6f}")
    print(f"macro_recall     = {evaluation.macro_recall:.6f}")
    print(f"macro_f1         = {evaluation.macro_f1:.6f}")
    print(f"log_loss         = {evaluation.log_loss:.6f}")
    print(f"brier_score      = {evaluation.brier_score:.6f}")
    print(
        "expected_calibration_error"
        f" = {evaluation.expected_calibration_error:.6f}"
    )

    print("confusion_matrix:")
    print(evaluation.confusion_matrix)

    print()
    print("Validation probability sample:")
    print(training_result.validation_probabilities.head(10).to_string())


def main() -> int:
    """Build real data, train both Phase 9 models, and evaluate them."""
    print("=" * 72)
    print("PHASE 9 — REAL MODEL TRAINING")
    print("=" * 72)

    result = _load_real_dataset()
    dataset = result.training_dataset

    print()
    print("Dataset")
    print("-" * 72)
    print(f"rows     = {len(dataset.data)}")
    print(f"features = {len(dataset.feature_columns)}")
    print(f"symbols  = {sorted(dataset.data['symbol'].astype(str).unique())}")

    logistic_result = train_baseline(dataset)
    _print_result(
        "LOGISTIC REGRESSION — CALIBRATED BASELINE",
        logistic_result,
        _validation_dataset(dataset),
    )

    random_forest_result = train_random_forest(dataset)
    _print_result(
        "RANDOM FOREST — CALIBRATED BENCHMARK",
        random_forest_result,
        _validation_dataset(dataset),
    )

    print()
    print("=" * 72)
    print("PHASE 9 REAL MODEL RUN COMPLETE")
    print("=" * 72)
    print("Note: metrics describe predictive quality only;")
    print("they are not trading-profitability results.")

    return 0


def _validation_dataset(dataset):
    """Return the same chronological validation partition used by training."""
    from ml.datasets.splitting import TemporalSplitConfig, temporal_split

    split = temporal_split(
        dataset,
        config=TemporalSplitConfig(),
    )
    return split.validation


if __name__ == "__main__":
    raise SystemExit(main())
