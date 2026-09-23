import pytest

from experiments.definition import ExperimentDefinition


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="S21-001",
        research_question="Does the frozen strategy remain causal under walk-forward evaluation?",
        hypothesis="Chronological evaluation preserves decision-time information boundaries.",
        failure_criterion="Any training/test timestamp overlap or future-field dependency.",
        dataset_version="dataset-2026-09-23",
        code_version="git:abc123",
        period_start="2026-01-01T09:15:00+05:30",
        period_end="2026-06-30T15:30:00+05:30",
        symbols=("ITC", "RELIANCE"),
        method="expanding walk-forward with 60-minute purge",
        fixed_parameters=(
            ("folds", "3"),
            ("purge_minutes", "60"),
        ),
        allowed_change=("model hyperparameters",),
    )


def test_experiment_definition_is_deterministic() -> None:
    first = _definition()
    second = _definition()

    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint() == second.fingerprint()
    assert len(first.fingerprint()) == 64


def test_experiment_definition_rejects_missing_identity() -> None:
    with pytest.raises(ValueError, match="dataset_version"):
        ExperimentDefinition(
            experiment_id="S21-001",
            research_question="question",
            hypothesis="hypothesis",
            failure_criterion="failure",
            dataset_version="",
            code_version="git:abc123",
            period_start="2026-01-01T09:15:00+05:30",
            period_end="2026-06-30T15:30:00+05:30",
            symbols=("ITC",),
            method="walk-forward",
        )


def test_experiment_definition_rejects_duplicate_fixed_parameter() -> None:
    with pytest.raises(ValueError, match="fixed_parameters"):
        ExperimentDefinition(
            experiment_id="S21-001",
            research_question="question",
            hypothesis="hypothesis",
            failure_criterion="failure",
            dataset_version="dataset-1",
            code_version="git:abc123",
            period_start="2026-01-01T09:15:00+05:30",
            period_end="2026-06-30T15:30:00+05:30",
            symbols=("ITC",),
            method="walk-forward",
            fixed_parameters=(("folds", "3"), ("folds", "5")),
        )
