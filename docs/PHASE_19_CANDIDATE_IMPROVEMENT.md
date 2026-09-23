# STOCK BOT — Phase 19 Candidate Improvement Engine

**Status:** IMPLEMENTED AS CONTROLLED RESEARCH PROPOSALS  
**Module:** `candidate_improvement/`

## Objective

Phase 19 converts validated Phase-18 learning evidence into a bounded candidate
strategy change that can be tested by the existing experiment pipeline.

The intended chain is:

```
Trade Journal
    ↓
Error Analysis
    ↓
Learning Evidence
    ↓
Candidate Improvement
    ↓
Frozen Experiment
    ↓
Backtest / OOS / Walk-forward / Paper
    ↓
Controlled approval
```

This matches the project roadmap requirement that a candidate must pass
Backtest → OOS → Walk-forward → Paper before it can become an approved model.

## Candidate contract

Each `CandidateImprovementProposal` records:

- candidate identity;
- hypothesis and rationale;
- source learning fingerprint;
- exact source trade IDs;
- baseline strategy fingerprint;
- explicit parameter changes;
- frozen experiment-definition fingerprint;
- evidence confidence and evidence count;
- immutable `PROPOSED` status.

The candidate has a deterministic SHA-256 fingerprint.

## Change boundary

Only the following StrategyConfig surfaces may be proposed:

- baseline minimum RVOL;
- baseline regime probability;
- prediction minimum probability;
- prediction minimum margin;
- prediction maximum age;
- expected-value threshold;
- maximum cost fraction;
- allowed regimes;
- prediction-direction alignment;
- analysis alignment;
- liquidity requirement.

Risk controls, execution controls, broker behavior, model weights, safety
controls, and live-enable state are outside the Phase-19 candidate surface.

The candidate's parameter-change keys must **exactly match** the frozen
`ExperimentDefinition.allowed_change` keys. This is enforced both when the
candidate is proposed and when it is later bound to the experiment.

## Candidate → research StrategyConfig

`CandidateImprovementEngine.materialize_strategy_config(...)` provides the
controlled bridge from a candidate to a research-only immutable
`StrategyConfig`.

It:

1. verifies the candidate is still `PROPOSED`;
2. verifies the candidate's baseline fingerprint matches the supplied baseline;
3. applies only the Phase-19 whitelist fields;
4. uses `dataclasses.replace`, so the baseline object is never mutated;
5. returns only a `StrategyConfig` — never Risk or Execution configuration.

The helper also supports an explicit expected baseline fingerprint, allowing the
experiment caller to fail closed if the baseline identity changed.

No authoritative production strategy is silently replaced by this operation.

## Candidate → experiment binding

`CandidateImprovementEngine.bind_to_experiment(...)` creates an immutable
`CandidateExperimentBinding` only when:

1. the candidate is still `PROPOSED`;
2. the supplied experiment-definition fingerprint exactly matches the
   fingerprint recorded by the candidate;
3. the candidate change-key set exactly equals
   `ExperimentDefinition.allowed_change`.

`execute_bound_experiment(...)` then routes the frozen definition through the
existing `ExperimentRunner`. The supplied executor owns experiment-specific
research configuration and must return an `ExperimentRecord` bound to the same
definition.

## Safety properties

Phase 19 does **not**:

- mutate StrategyConfig;
- mutate RiskConfig;
- retrain model weights;
- promote a candidate;
- authorize an order;
- contact a broker;
- enable live execution.

Validation returns a separate `CandidateValidation` object. A validated
candidate remains `PROPOSED`; promotion requires the downstream experimental
and governance gates.

## Evidence binding

A candidate cannot be created without:

1. a concrete `LearningExperience`;
2. source trade IDs;
3. a baseline strategy fingerprint;
4. a frozen `ExperimentDefinition`;
5. a non-empty declared change whitelist.

This prevents an improvement proposal from becoming detached from the
observed evidence or from the experiment specification that is intended to
test it.

## Important distinction

A candidate is a **hypothesis**, not proof of improvement.

Phase 19 does not claim that a proposed change improves profitability,
risk-adjusted returns, drawdown, robustness, or live performance. Those claims
require the existing backtest, OOS, walk-forward, paper-evidence, and readiness
controls.
