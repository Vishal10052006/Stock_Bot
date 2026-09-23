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
