import pytest

from candidate_improvement import (
    CandidateExperimentBinding,
    CandidateImprovementEngine,
    CandidateStatus,
)
from experiments import ExperimentDefinition, ExperimentRecord
from learning import ErrorClass, LearningExperience, LearningPattern


def _experience() -> LearningExperience:
    return LearningExperience(
        pattern=LearningPattern.LOW_RVOL_SIDEWAYS_BREAKOUT,
        error_class=ErrorClass.CONTEXT_LOSS_CLUSTER,
        evidence_count=3,
        population_count=4,
        occurrence_rate=0.75,
        confidence=0.28,
        average_reward=-0.5,
        total_reward=-1.5,
        source_trade_ids=("T1", "T2", "T3"),
        rationale="Observed losses in low-RVOL sideways breakouts.",
        conditions=(
            "market_regime in {SIDEWAYS,RANGE}",
            "rvol_20<0.8",
            "breakout=True",
        ),
        average_net_pnl=-10.0,
        total_net_pnl=-30.0,
        detail="Repeated contextual loss cluster.",
    )


def _definition(*, allowed_change=("baseline.minimum_rvol",)) -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="EXP-P19-001",
        research_question="Does a higher RVOL gate reduce the observed failure pattern?",
        hypothesis="A higher RVOL threshold may reduce low-RVOL breakout losses.",
        failure_criterion="Reject if OOS or walk-forward evidence deteriorates.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        period_start="2025-01-01",
        period_end="2026-01-01",
        symbols=("ITC",),
        method="backtest_oos_walk_forward",
        allowed_change=allowed_change,
    )


def _candidate() -> tuple[object, ExperimentDefinition]:
    definition = _definition()
    candidate = CandidateImprovementEngine().propose(
        _experience(),
        baseline_strategy_fingerprint="strategy-fp",
        parameter_changes={"baseline.minimum_rvol": 1.10},
        experiment_definition=definition,
        candidate_id="CAND-001",
    )
    return candidate, definition


def _record(definition: ExperimentDefinition) -> ExperimentRecord:
    return ExperimentRecord.from_definition(
        definition,
        observations=10,
        interpretation="Structural test record.",
        decision="INCONCLUSIVE",
    )


def test_candidate_is_evidence_bound_and_immutable() -> None:
    candidate, definition = _candidate()

    assert candidate.status is CandidateStatus.PROPOSED
    assert candidate.source_trade_ids == ("T1", "T2", "T3")
    assert candidate.experiment_definition_fingerprint == definition.fingerprint()
    assert candidate.parameter_changes == (
        ("baseline.minimum_rvol", "1.1"),
    )
    assert candidate.fingerprint == candidate.fingerprint


def test_candidate_rejects_undeclared_experiment_change() -> None:
    with pytest.raises(ValueError, match="not declared"):
        CandidateImprovementEngine().propose(
            _experience(),
            baseline_strategy_fingerprint="strategy-fp",
            parameter_changes={"prediction_min_margin": 0.1},
            experiment_definition=_definition(),
            candidate_id="CAND-002",
        )


def test_candidate_rejects_non_strategy_fields() -> None:
    definition = _definition(allowed_change=("risk.risk_per_trade",))
    with pytest.raises(ValueError, match="forbidden"):
        CandidateImprovementEngine().propose(
            _experience(),
            baseline_strategy_fingerprint="strategy-fp",
            parameter_changes={"risk.risk_per_trade": 0.004},
            experiment_definition=definition,
            candidate_id="CAND-003",
        )


def test_candidate_rejects_experiment_with_extra_undeclared_change() -> None:
    definition = _definition(
        allowed_change=("baseline.minimum_rvol", "prediction_min_margin"),
    )
    with pytest.raises(ValueError, match="not present in candidate"):
        CandidateImprovementEngine().propose(
            _experience(),
            baseline_strategy_fingerprint="strategy-fp",
            parameter_changes={"baseline.minimum_rvol": 1.10},
            experiment_definition=definition,
            candidate_id="CAND-004",
        )


def test_candidate_binds_to_exact_frozen_experiment() -> None:
    candidate, definition = _candidate()

    binding = CandidateImprovementEngine.bind_to_experiment(candidate, definition)

    assert isinstance(binding, CandidateExperimentBinding)
    assert binding.candidate_fingerprint == candidate.fingerprint
    assert binding.experiment_definition_fingerprint == definition.fingerprint()
    assert binding.parameter_changes == candidate.parameter_changes
    assert candidate.status is CandidateStatus.PROPOSED


def test_candidate_execution_routes_through_experiment_runner() -> None:
    candidate, definition = _candidate()
    calls: list[str] = []

    def executor(received: ExperimentDefinition) -> ExperimentRecord:
        calls.append(received.fingerprint())
        return _record(received)

    result = CandidateImprovementEngine.execute_bound_experiment(
        candidate,
        definition,
        executor,
    )

    assert result.binding.candidate_fingerprint == candidate.fingerprint
    assert result.execution.definition.fingerprint() == definition.fingerprint()
    assert result.execution.record.definition_fingerprint == definition.fingerprint()
    assert calls == [definition.fingerprint()]
    assert candidate.status is CandidateStatus.PROPOSED


def test_candidate_execution_rejects_wrong_record_identity() -> None:
    candidate, definition = _candidate()
    different_definition = _definition()
    different_definition = ExperimentDefinition(
        experiment_id="EXP-P19-WRONG",
        research_question=different_definition.research_question,
        hypothesis=different_definition.hypothesis,
        failure_criterion=different_definition.failure_criterion,
        dataset_version=different_definition.dataset_version,
        code_version=different_definition.code_version,
        period_start=different_definition.period_start,
        period_end=different_definition.period_end,
        symbols=different_definition.symbols,
        method=different_definition.method,
        allowed_change=different_definition.allowed_change,
    )

    def executor(_: ExperimentDefinition) -> ExperimentRecord:
        return _record(different_definition)

    with pytest.raises(ValueError, match="record fingerprint"):
        CandidateImprovementEngine.execute_bound_experiment(
            candidate,
            definition,
            executor,
        )


def test_candidate_binding_rejects_definition_fingerprint_mismatch() -> None:
    candidate, _ = _candidate()
    different_definition = ExperimentDefinition(
        experiment_id="EXP-P19-002",
        research_question="Different question",
        hypothesis="Different hypothesis",
        failure_criterion="Different failure criterion",
        dataset_version="dataset-v2",
        code_version="code-v2",
        period_start="2025-01-01",
        period_end="2026-01-01",
        symbols=("ITC",),
        method="backtest_oos_walk_forward",
        allowed_change=("baseline.minimum_rvol",),
    )

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        CandidateImprovementEngine.bind_to_experiment(candidate, different_definition)


def test_validation_never_promotes_candidate() -> None:
    candidate, _ = _candidate()

    result = CandidateImprovementEngine.validate(candidate, minimum_evidence=3)
    assert result.accepted is True
    assert candidate.status is CandidateStatus.PROPOSED


def test_validation_rejects_insufficient_evidence() -> None:
    candidate, _ = _candidate()

    result = CandidateImprovementEngine.validate(candidate, minimum_evidence=4)
    assert result.accepted is False
    assert "insufficient evidence" in result.reasons
