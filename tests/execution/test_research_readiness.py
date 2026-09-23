import pandas as pd
import pytest

from backtesting.engine import BacktestResult
from execution.research_readiness import build_research_readiness_evidence
from experiments.definition import ExperimentDefinition
from experiments.executor import (
    ExperimentExecutionInputs,
    execute_validation_experiment_with_lineage,
)
from experiments.lineage import LineageRecord
from ml.datasets.models import TrainingDataset


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="EXP-RESEARCH-READINESS",
        research_question="Does the frozen validation boundary remain causal?",
        hypothesis="The validation pipeline preserves temporal ordering.",
        failure_criterion="Any temporal validation boundary fails.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        period_start="2026-01-01",
        period_end="2026-09-01",
        symbols=("ITC",),
        method="causal-validation",
        fixed_parameters=(("horizon", 1),),
        allowed_change=("horizon",),
    )


def _inputs() -> ExperimentExecutionInputs:
    timestamps = pd.date_range(
        "2026-09-01 09:15:00+00:00",
        periods=200,
        freq="5min",
    )
    data = pd.DataFrame({"timestamp": timestamps, "feature": range(200), "label": ["LONG_SUCCESS", "NO_EDGE"] * 100})

    def predictor(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        return pd.Series(["LONG_SUCCESS"] * len(test), index=test.index)

    def evaluator(train: pd.DataFrame, test: pd.DataFrame) -> object:
        return {"test_rows": len(test)}

    return ExperimentExecutionInputs(
        oos_dataset=TrainingDataset(data=data, feature_columns=("feature",)),
        oos_predictor=predictor,
        walk_forward_data=data,
        walk_forward_evaluator=evaluator,
        folds=3,
        purge_minutes=60,
    )


def test_research_readiness_evidence_binds_one_execution_lineage() -> None:
    execution = execute_validation_experiment_with_lineage(
        _definition(),
        _inputs(),
    )

    evidence = build_research_readiness_evidence(
        execution,
        validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
        include_backtest=False,
    )

    assert [item.gate for item in evidence] == [
        "baseline_validated",
        "model_validated",
        "oos_validated",
        "walk_forward_validated",
    ]
    assert all(
        item.dataset_version == execution.lineage.dataset_version
        for item in evidence
    )
    assert all(
        item.code_version == execution.lineage.code_version
        for item in evidence
    )

    artifacts = dict(execution.lineage.artifact_fingerprints)
    by_gate = {item.gate: item for item in evidence}
    assert by_gate["oos_validated"].artifact_fingerprint == artifacts["oos"]
    assert (
        by_gate["walk_forward_validated"].artifact_fingerprint
        == artifacts["walk_forward"]
    )
    assert (
        by_gate["baseline_validated"].artifact_fingerprint
        == execution.lineage.lineage_id
    )
    assert (
        by_gate["model_validated"].artifact_fingerprint
        == execution.lineage.lineage_id
    )


def test_research_readiness_rejects_tampered_lineage_artifact() -> None:
    execution = execute_validation_experiment_with_lineage(
        _definition(),
        _inputs(),
    )
    artifacts = dict(execution.lineage.artifact_fingerprints)
    tampered = LineageRecord(
        experiment_id=execution.lineage.experiment_id,
        definition_fingerprint=execution.lineage.definition_fingerprint,
        record_fingerprint=execution.lineage.record_fingerprint,
        dataset_version=execution.lineage.dataset_version,
        code_version=execution.lineage.code_version,
        artifact_fingerprints=tuple(
            sorted(
                {
                    "oos": "a" * 64,
                    "walk_forward": artifacts["walk_forward"],
                }.items()
            )
        ),
    ).with_computed_id()
    tampered_execution = execution.__class__(
        record=execution.record,
        lineage=tampered,
        oos_report=execution.oos_report,
        walk_forward_report=execution.walk_forward_report,
        backtest_result=execution.backtest_result,
        backtest_metrics=execution.backtest_metrics,
    )

    with pytest.raises(ValueError, match="does not match experiment lineage"):
        build_research_readiness_evidence(
            tampered_execution,
            validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
            include_backtest=False,
        )


def test_research_readiness_requires_explicit_backtest() -> None:
    execution = execute_validation_experiment_with_lineage(
        _definition(),
        _inputs(),
    )

    with pytest.raises(ValueError, match="requires a backtest result"):
        build_research_readiness_evidence(
            execution,
            validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
        )


def test_research_readiness_binds_backtest_artifact() -> None:
    execution = execute_validation_experiment_with_lineage(
        _definition(),
        _inputs(),
    )
    backtest = BacktestResult(steps=(), outcomes=())
    artifacts = dict(execution.lineage.artifact_fingerprints)
    lineage = LineageRecord(
        experiment_id=execution.lineage.experiment_id,
        definition_fingerprint=execution.lineage.definition_fingerprint,
        record_fingerprint=execution.lineage.record_fingerprint,
        dataset_version=execution.lineage.dataset_version,
        code_version=execution.lineage.code_version,
        artifact_fingerprints=tuple(
            sorted(
                {
                    "backtest": backtest.fingerprint,
                    "oos": artifacts["oos"],
                    "walk_forward": artifacts["walk_forward"],
                }.items()
            )
        ),
    ).with_computed_id()
    execution_with_backtest = execution.__class__(
        record=execution.record,
        lineage=lineage,
        oos_report=execution.oos_report,
        walk_forward_report=execution.walk_forward_report,
        backtest_result=backtest,
        backtest_metrics=None,
    )

    evidence = build_research_readiness_evidence(
        execution_with_backtest,
        validated_at=pd.Timestamp("2026-09-23T10:00:00Z").to_pydatetime(),
    )

    backtest_evidence = next(
        item for item in evidence if item.gate == "realistic_backtest_validated"
    )
    assert backtest_evidence.artifact_fingerprint == backtest.fingerprint
    assert backtest_evidence.evidence_kind == "backtest"
