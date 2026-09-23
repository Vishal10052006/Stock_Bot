import pytest
from dataclasses import replace

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


@pytest.mark.parametrize(
    ("field", "value", "assert_changed"),
    [
        ("baseline.minimum_rvol", 1.10, lambda c: c.baseline.minimum_rvol == 1.10),
        (
            "baseline.minimum_regime_probability",
            0.65,
            lambda c: c.baseline.minimum_regime_probability == 0.65,
        ),
        ("prediction_min_probability", 0.70, lambda c: c.prediction_min_probability == 0.70),
        ("prediction_min_margin", 0.15, lambda c: c.prediction_min_margin == 0.15),
        ("prediction_max_age_seconds", 120, lambda c: c.prediction_max_age_seconds == 120),
        ("expected_value_threshold", 0.002, lambda c: c.expected_value_threshold == 0.002),
        ("max_cost_fraction", 0.001, lambda c: c.max_cost_fraction == 0.001),
        (
            "allowed_regimes",
            ("TREND_UP", "RANGE"),
            lambda c: c.allowed_regimes == ("TREND_UP", "RANGE"),
        ),
        (
            "require_prediction_direction_alignment",
            False,
            lambda c: c.require_prediction_direction_alignment is False,
        ),
        ("require_analysis_alignment", False, lambda c: c.require_analysis_alignment is False),
        (
            "require_liquidity_when_present",
            False,
            lambda c: c.require_liquidity_when_present is False,
        ),
    ],
)
def test_all_whitelisted_strategy_parameters_materialize(
    field: str,
    value: object,
    assert_changed,
) -> None:
    baseline = _baseline()
    definition = _definition(allowed_change=(field,))
    candidate, _ = _candidate(parameter_changes={field: value}, definition=definition)

    baseline_before = CandidateImprovementEngine.strategy_config_fingerprint(baseline)
    materialized = CandidateImprovementEngine.materialize_strategy_config(candidate, baseline)

    assert assert_changed(materialized)
    assert CandidateImprovementEngine.strategy_config_fingerprint(baseline) == baseline_before
    assert materialized is not baseline


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "risk.risk_per_trade",
        "risk.max_daily_loss",
        "execution.order_type",
        "execution.quantity",
        "safety.live_execution_enabled",
            "model.weights",
    ],
)
def test_candidate_rejects_non_strategy_control_surfaces(forbidden_field: str) -> None:
    with pytest.raises(ValueError, match="forbidden"):
        CandidateImprovementEngine().propose(
            _experience(),
            baseline_strategy_fingerprint="strategy-fp",
            parameter_changes={forbidden_field: 1},
            experiment_definition=_definition(allowed_change=(forbidden_field,)),
            candidate_id=f"CAND-{forbidden_field.replace('.', '-')}",
        )


def test_strategy_fingerprint_is_reproducible_and_changes_on_strategy_change() -> None:
    baseline_a = _baseline()
    baseline_b = _baseline()

    fingerprint_a = CandidateImprovementEngine.strategy_config_fingerprint(baseline_a)
    fingerprint_b = CandidateImprovementEngine.strategy_config_fingerprint(baseline_b)

    assert fingerprint_a == fingerprint_b
    assert len(fingerprint_a) == 64

    changed = CandidateImprovementEngine.materialize_strategy_config(
        _candidate()[0],
        baseline_a,
    )
    assert CandidateImprovementEngine.strategy_config_fingerprint(changed) != fingerprint_a


def test_learning_evidence_identity_is_reproducible_and_carries_trade_identity() -> None:
    experience = _experience()
    candidate, _ = _candidate()

    assert candidate.source_learning_fingerprint == (
        CandidateImprovementEngine._learning_fingerprint(experience)
    )
    assert candidate.source_trade_ids == experience.source_trade_ids

    altered = replace(experience, rationale="Different evidence rationale.")
    assert (
        CandidateImprovementEngine._learning_fingerprint(altered)
        != candidate.source_learning_fingerprint
    )


def test_candidate_and_binding_fingerprints_are_deterministic() -> None:
    candidate_a, definition_a = _candidate()
    candidate_b, definition_b = _candidate()

    binding_a = CandidateImprovementEngine.bind_to_experiment(candidate_a, definition_a)
    binding_b = CandidateImprovementEngine.bind_to_experiment(candidate_b, definition_b)

    assert candidate_a.fingerprint == candidate_b.fingerprint
    assert binding_a.fingerprint == binding_b.fingerprint


def test_candidate_execution_boundary_exposes_no_risk_or_execution_authority() -> None:
    import inspect

    signature = inspect.signature(CandidateImprovementEngine.execute_bound_experiment)
    parameter_names = tuple(signature.parameters)
    assert parameter_names == (
        "candidate",
        "experiment_definition",
        "baseline_config",
        "executor",
    )

    annotations = signature.parameters["executor"].annotation
    assert "StrategyConfig" in str(annotations)
    assert "RiskDecision" not in str(annotations)
    assert "ExecutionAuthorization" not in str(annotations)


def test_candidate_execution_preserves_proposed_status_and_does_not_promote() -> None:
    candidate, definition = _candidate()
    baseline = _baseline()

    def executor(received: ExperimentDefinition, strategy: StrategyConfig) -> ExperimentRecord:
        assert strategy.baseline.minimum_rvol == 1.10
        return _record(received)

    result = CandidateImprovementEngine.execute_bound_experiment(
        candidate,
        definition,
        baseline,
        executor,
    )

    assert result.execution.record.decision == "INCONCLUSIVE"
    assert candidate.status is CandidateStatus.PROPOSED


