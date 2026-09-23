import pytest

from candidate_improvement import (
    CandidateExperimentBinding,
    CandidateImprovementEngine,
    CandidateStatus,
)
from experiments import ExperimentDefinition, ExperimentRecord
from learning import ErrorClass, LearningExperience, LearningPattern
from trading.strategy.models import BaselineStrategyConfig, StrategyConfig


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


def _baseline() -> StrategyConfig:
    return StrategyConfig(
        strategy_id="baseline_trend_v1",
        strategy_version="STRAT-v1.0",
        baseline=BaselineStrategyConfig(
            minimum_rvol=1.0,
            minimum_regime_probability=0.50,
            strategy_version="v1.0",
        ),
    )


def _candidate(
    *,
    parameter_changes: dict[str, object] | None = None,
    definition: ExperimentDefinition | None = None,
) -> tuple[object, ExperimentDefinition]:
    definition = definition or _definition(
        allowed_change=tuple((parameter_changes or {"baseline.minimum_rvol": 1.10}).keys())
    )
    candidate = CandidateImprovementEngine().propose(
        _experience(),
        baseline_strategy_fingerprint=CandidateImprovementEngine.strategy_config_fingerprint(
            _baseline()
        ),
        parameter_changes=parameter_changes or {"baseline.minimum_rvol": 1.10},
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
    assert candidate.parameter_changes == (("baseline.minimum_rvol", "1.1"),)
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
    assert binding.baseline_strategy_fingerprint == candidate.baseline_strategy_fingerprint
    assert binding.parameter_changes == candidate.parameter_changes
    assert candidate.status is CandidateStatus.PROPOSED


def test_candidate_materializes_research_strategy_without_mutating_baseline() -> None:
    baseline = _baseline()
    baseline_fingerprint = CandidateImprovementEngine.strategy_config_fingerprint(baseline)
    candidate, _ = _candidate()

    materialized = CandidateImprovementEngine.materialize_strategy_config(
        candidate,
        baseline,
        expected_baseline_fingerprint=baseline_fingerprint,
    )

    assert materialized.baseline.minimum_rvol == 1.10
    assert baseline.baseline.minimum_rvol == 1.0
    assert (
        CandidateImprovementEngine.strategy_config_fingerprint(baseline)
        == baseline_fingerprint
    )
    assert materialized.strategy_version == baseline.strategy_version


def test_materialization_rejects_wrong_baseline_identity() -> None:
    candidate, _ = _candidate()
    with pytest.raises(ValueError, match="baseline strategy"):
        CandidateImprovementEngine.materialize_strategy_config(
            candidate,
            StrategyConfig(strategy_version="STRAT-v9.0"),
        )


def test_candidate_execution_materializes_candidate_strategy_and_routes_through_runner() -> None:
    candidate, definition = _candidate()
    baseline = _baseline()
    calls: list[tuple[str, float, str]] = []

    def executor(received: ExperimentDefinition, strategy: StrategyConfig) -> ExperimentRecord:
        calls.append(
            (
                received.fingerprint(),
                strategy.baseline.minimum_rvol,
                CandidateImprovementEngine.strategy_config_fingerprint(strategy),
            )
        )
        return _record(received)

    result = CandidateImprovementEngine.execute_bound_experiment(
        candidate,
        definition,
        baseline,
        executor,
    )

    assert result.binding.candidate_fingerprint == candidate.fingerprint
    assert result.binding.baseline_strategy_fingerprint == (
        CandidateImprovementEngine.strategy_config_fingerprint(baseline)
    )
    assert result.execution.definition.fingerprint() == definition.fingerprint()
    assert result.execution.record.definition_fingerprint == definition.fingerprint()
    assert calls == [
        (
            definition.fingerprint(),
            1.10,
            CandidateImprovementEngine.strategy_config_fingerprint(
                CandidateImprovementEngine.materialize_strategy_config(candidate, baseline)
            ),
        )
    ]
    assert baseline.baseline.minimum_rvol == 1.0
    assert candidate.status is CandidateStatus.PROPOSED


def test_candidate_execution_rejects_baseline_identity_before_executor() -> None:
    candidate, definition = _candidate()
    calls = 0

    def executor(_: ExperimentDefinition, __: StrategyConfig) -> ExperimentRecord:
        nonlocal calls
        calls += 1
        return _record(definition)

    with pytest.raises(ValueError, match="baseline strategy"):
        CandidateImprovementEngine.execute_bound_experiment(
            candidate,
            definition,
            StrategyConfig(strategy_version="STRAT-v9.0"),
            executor,
        )
    assert calls == 0


def test_candidate_execution_rejects_wrong_record_identity() -> None:
    candidate, definition = _candidate()
    different_definition = ExperimentDefinition(
        experiment_id="EXP-P19-WRONG",
        research_question=definition.research_question,
        hypothesis=definition.hypothesis,
        failure_criterion=definition.failure_criterion,
        dataset_version=definition.dataset_version,
        code_version=definition.code_version,
        period_start=definition.period_start,
        period_end=definition.period_end,
        symbols=definition.symbols,
        method=definition.method,
        allowed_change=definition.allowed_change,
    )

    def executor(_: ExperimentDefinition, __: StrategyConfig) -> ExperimentRecord:
        return _record(different_definition)

    with pytest.raises(ValueError, match="record fingerprint"):
        CandidateImprovementEngine.execute_bound_experiment(
            candidate,
            definition,
            _baseline(),
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
