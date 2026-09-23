import pytest

from experiments import ExperimentDefinition, ExperimentRecord, ExperimentRunner


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="S21-002",
        research_question="Does the frozen pipeline preserve chronology?",
        hypothesis="Explicit execution preserves the information boundary.",
        failure_criterion="The executor returns a record bound to another definition.",
        dataset_version="dataset-1",
        code_version="git:abc123",
        period_start="2026-01-01T09:15:00+05:30",
        period_end="2026-06-30T15:30:00+05:30",
        symbols=("ITC",),
        method="walk-forward",
    )


def test_runner_executes_once_and_binds_result() -> None:
    definition = _definition()
    calls = []

    def executor(received: ExperimentDefinition) -> ExperimentRecord:
        calls.append(received.experiment_id)
        return ExperimentRecord.from_definition(
            received,
            observations=20,
        )

    execution = ExperimentRunner(definition).run(executor)

    assert calls == ["S21-002"]
    assert execution.record.definition_fingerprint == definition.fingerprint()


def test_runner_rejects_unbound_record() -> None:
    definition = _definition()
    other = ExperimentDefinition(
        experiment_id="OTHER",
        research_question="q",
        hypothesis="h",
        failure_criterion="f",
        dataset_version="dataset-1",
        code_version="git:abc123",
        period_start="2026-01-01T09:15:00+05:30",
        period_end="2026-06-30T15:30:00+05:30",
        symbols=("ITC",),
        method="walk-forward",
    )

    def executor(_: ExperimentDefinition) -> ExperimentRecord:
        return ExperimentRecord.from_definition(other, observations=1)

    with pytest.raises(ValueError, match="fingerprint"):
        ExperimentRunner(definition).run(executor)
