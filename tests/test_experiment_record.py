from experiments.definition import ExperimentDefinition
from experiments.record import ExperimentRecord


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="S21-001",
        research_question="Does the frozen strategy remain causal?",
        hypothesis="Chronological evaluation preserves the information boundary.",
        failure_criterion="Any future observation enters an earlier decision.",
        dataset_version="dataset-1",
        code_version="git:abc123",
        period_start="2026-01-01T09:15:00+05:30",
        period_end="2026-06-30T15:30:00+05:30",
        symbols=("ITC",),
        method="expanding walk-forward",
    )


def test_record_is_bound_to_definition_fingerprint() -> None:
    definition = _definition()
    record = ExperimentRecord.from_definition(
        definition,
        observations=100,
        label_distribution={"LONG_SUCCESS": 40, "NO_EDGE": 60},
        decision="INCONCLUSIVE",
    )

    assert record.definition_fingerprint == definition.fingerprint()
    assert record.to_dict()["label_distribution"] == {
        "LONG_SUCCESS": 40,
        "NO_EDGE": 60,
    }


def test_record_serialization_is_deterministic() -> None:
    definition = _definition()
    first = ExperimentRecord.from_definition(
        definition,
        observations=10,
        baseline_results={"accuracy": 0.5},
        decision="KEEP",
    )
    second = ExperimentRecord.from_definition(
        definition,
        observations=10,
        baseline_results={"accuracy": 0.5},
        decision="KEEP",
    )

    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint() == second.fingerprint()
