import pandas as pd

from experiments.definition import ExperimentDefinition
from experiments.executor import (
    ExperimentExecutionInputs,
    execute_validation_experiment_with_lineage,
)
from ml.datasets.models import TrainingDataset


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="EXP-LINEAGE-1",
        research_question="Does the validation pipeline preserve chronology?",
        hypothesis="Chronological validation remains isolated.",
        failure_criterion="Any future leakage is detected.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        period_start="2026-01-01",
        period_end="2026-01-02",
        symbols=("ITC",),
        method="oos-walk-forward",
    )


def _inputs() -> ExperimentExecutionInputs:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=200,
        freq="5min",
        tz="Asia/Kolkata",
    )
    data = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * len(timestamps),
            "feature": range(len(timestamps)),
            "label": ["LONG_SUCCESS"] * len(timestamps),
        }
    )

    dataset = TrainingDataset(
        data=data,
        feature_columns=("feature",),
    )

    def predictor(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        return pd.Series(["LONG_SUCCESS"] * len(test))

    def evaluator(train: pd.DataFrame, test: pd.DataFrame) -> object:
        return {"test_rows": len(test)}

    return ExperimentExecutionInputs(
        oos_dataset=dataset,
        oos_predictor=predictor,
        walk_forward_data=data,
        walk_forward_evaluator=evaluator,
        folds=3,
        purge_minutes=5,
    )


def test_validation_execution_binds_oos_and_walk_forward_artifacts() -> None:
    execution = execute_validation_experiment_with_lineage(
        _definition(),
        _inputs(),
    )

    assert execution.record.definition_fingerprint == _definition().fingerprint()
    assert execution.lineage.record_fingerprint == execution.record.fingerprint()
    assert execution.lineage.dataset_version == "dataset-v1"
    assert execution.lineage.code_version == "code-v1"

    artifacts = dict(execution.lineage.artifact_fingerprints)
    assert artifacts["oos"] == execution.oos_report.fingerprint
    assert artifacts["walk_forward"] == execution.walk_forward_report.fingerprint
    assert execution.lineage.lineage_id == execution.lineage.computed_id()


def test_lineage_identity_changes_when_artifact_identity_changes() -> None:
    first = execute_validation_experiment_with_lineage(
        _definition(),
        _inputs(),
    )
    second_definition = ExperimentDefinition(
        **{
            **_definition().to_dict(),
            "method": "oos-walk-forward-v2",
        }
    )
    second = execute_validation_experiment_with_lineage(
        second_definition,
        _inputs(),
    )

    assert first.lineage.lineage_id != second.lineage.lineage_id
