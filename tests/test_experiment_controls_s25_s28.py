import pandas as pd
import pytest

from experiments import (
    ExperimentDefinition,
    ExperimentRecord,
    evaluate_experiment_record,
)
from experiments.failure_analysis import analyze_experiment_failure
from experiments.lineage import build_lineage
from experiments.monitoring import (
    MonitoringPolicy,
    MonitoringSnapshot,
    evaluate_monitoring,
)
from experiments.self_learning import (
    LearningProposal,
    validate_learning_proposal,
)


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="S25-001",
        research_question="Does the control boundary remain reproducible?",
        hypothesis="Frozen inputs produce auditable evidence.",
        failure_criterion="Any integrity violation blocks reuse.",
        dataset_version="dataset-v1",
        code_version="git:test",
        period_start="2026-01-01T00:00:00+00:00",
        period_end="2026-01-02T00:00:00+00:00",
        symbols=("ITC",),
        method="oos-walk-forward",
        allowed_change=("prediction_threshold",),
    )


def _record() -> ExperimentRecord:
    return ExperimentRecord.from_definition(
        _definition(),
        observations=10,
        baseline_results={"oos": {"test_rows": 5}},
        model_results={"walk_forward": {"folds": 2}},
        limitations=("synthetic test data",),
        decision="INCONCLUSIVE",
    )


def test_failure_analysis_reports_structural_findings() -> None:
    record = _record()
    evaluation = evaluate_experiment_record(record)
    report = analyze_experiment_failure(record, evaluation=evaluation)

    codes = {finding.code for finding in report.findings}
    assert "INCONCLUSIVE_RESULT" in codes
    assert "RECORDED_LIMITATIONS" in codes


def test_monitoring_reports_threshold_breaches() -> None:
    report = evaluate_monitoring(
        MonitoringSnapshot(
            total_events=100,
            failed_events=10,
            stale_events=20,
            reference_probabilities=(0.1,) * 100,
            current_probabilities=(0.9,) * 100,
        ),
        policy=MonitoringPolicy(
            max_error_rate=0.05,
            max_stale_rate=0.10,
            max_prediction_psi=0.20,
        ),
    )

    assert not report.healthy
    assert "ERROR_RATE_EXCEEDED" in report.alerts
    assert "STALE_RATE_EXCEEDED" in report.alerts
    assert "PREDICTION_DRIFT_EXCEEDED" in report.alerts


def test_lineage_binds_definition_and_record() -> None:
    definition = _definition()
    record = _record()
    lineage = build_lineage(
        definition,
        record,
        artifact_fingerprints={"dataset": "abc123"},
    )

    assert lineage.definition_fingerprint == definition.fingerprint()
    assert lineage.record_fingerprint == record.fingerprint()
    assert len(lineage.lineage_id) == 64
    assert lineage.computed_id() == lineage.lineage_id


def test_lineage_rejects_record_from_other_definition() -> None:
    definition = _definition()
    other = ExperimentDefinition(
        experiment_id="OTHER",
        research_question=definition.research_question,
        hypothesis=definition.hypothesis,
        failure_criterion=definition.failure_criterion,
        dataset_version=definition.dataset_version,
        code_version=definition.code_version,
        period_start=definition.period_start,
        period_end=definition.period_end,
        symbols=definition.symbols,
        method=definition.method,
    )
    with pytest.raises(ValueError, match="does not belong"):
        build_lineage(definition, ExperimentRecord.from_definition(other, observations=1),)


def test_learning_proposal_requires_explicitly_allowed_changes() -> None:
    definition = _definition()
    record = _record()
    evaluation = evaluate_experiment_record(record)
    proposal = LearningProposal(
        proposal_id="LP-001",
        source_experiment_fingerprint=definition.fingerprint(),
        requested_changes=(("prediction_threshold", "0.60"),),
        rationale="Test a predeclared threshold change.",
    )

    result = validate_learning_proposal(
        proposal,
        definition,
        record,
        evaluation,
    )

    assert result.status == "VALIDATION_REQUIRED"
    assert result.can_change_frozen_configuration is False


def test_learning_proposal_cannot_change_unapproved_field() -> None:
    definition = _definition()
    record = _record()
    evaluation = evaluate_experiment_record(record)
    proposal = LearningProposal(
        proposal_id="LP-002",
        source_experiment_fingerprint=definition.fingerprint(),
        requested_changes=(("risk_per_trade", "0.01"),),
        rationale="Attempt an unapproved change.",
    )

    result = validate_learning_proposal(
        proposal,
        definition,
        record,
        evaluation,
    )

    assert result.status == "BLOCKED"
    assert "CHANGE_NOT_ALLOWED:risk_per_trade" in result.reasons
