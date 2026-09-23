import pandas as pd

from experiments import (
    ExperimentDefinition,
    ExperimentExecutionInputs,
    execute_validation_experiment,
)
from ml.datasets.models import TrainingDataset


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="S21-003",
        research_question="Does the validation boundary execute causally?",
        hypothesis="Temporal validation remains separated by purge windows.",
        failure_criterion="Any validation contract raises a chronology violation.",
        dataset_version="dataset-1",
        code_version="git:test",
        period_start="2026-01-01T09:15:00+05:30",
        period_end="2026-01-05T15:30:00+05:30",
        symbols=("ITC",),
        method="oos-and-walk-forward",
    )


def _dataset() -> TrainingDataset:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=30,
        freq="5min",
        tz="UTC",
    )
    data = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * len(timestamps),
            "feature": range(len(timestamps)),
            "label": [0, 1] * 15,
        }
    )
    return TrainingDataset(data=data, feature_columns=("feature",))


def test_validation_executor_records_explicit_boundaries() -> None:
    data = _dataset()
    wf_data = data.data.copy()

    def predictor(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        return pd.Series([0] * len(test), index=test.index)

    def evaluator(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, int]:
        return {"test_rows": len(test)}

    record = execute_validation_experiment(
        _definition(),
        ExperimentExecutionInputs(
            oos_dataset=data,
            oos_predictor=predictor,
            walk_forward_data=wf_data,
            walk_forward_evaluator=evaluator,
            folds=2,
            purge_minutes=1,
        ),
    )

    assert record.decision == "INCONCLUSIVE"
    assert record.baseline_results["oos"]["test_rows"] > 0
    assert record.model_results["walk_forward"]["folds"] == 2


def test_validation_executor_can_run_authoritative_backtest() -> None:
    data = _dataset()
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=2,
        freq="5min",
        tz="UTC",
    )
    backtest_rows = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC", "ITC"],
            "close": [100.0, 101.0],
            "atr_14": [2.0, 2.0],
            "swing_low": [96.0, 96.0],
            "swing_high": [104.0, 104.0],
            "support_20": [95.0, 95.0],
            "resistance_20": [105.0, 105.0],
            "regime": ["TREND_UP", "TREND_UP"],
            "regime_probability": [0.90, 0.90],
            "vwap_distance_pct": [1.0, 1.0],
            "rvol_20": [1.5, 1.5],
            "higher_high": [True, True],
            "higher_low": [True, True],
            "lower_low": [False, False],
            "lower_high": [False, False],
        }
    )

    def predictor(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        return pd.Series([0] * len(test), index=test.index)

    def evaluator(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, int]:
        return {"test_rows": len(test)}

    record = execute_validation_experiment(
        _definition(),
        ExperimentExecutionInputs(
            oos_dataset=data,
            oos_predictor=predictor,
            walk_forward_data=data.data.copy(),
            walk_forward_evaluator=evaluator,
            folds=2,
            purge_minutes=1,
            backtest_rows=backtest_rows,
        ),
    )

    assert "backtest" in record.baseline_results
    assert record.baseline_results["backtest"]["completed_trades"] == 1
