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

## Candidate → experiment binding

`CandidateImprovementEngine.bind_to_experiment(...)` creates an immutable
`CandidateExperimentBinding` only when:

1. the candidate is still `PROPOSED`;
2. the supplied experiment-definition fingerprint exactly matches the
   fingerprint recorded by the candidate;
3. the candidate change-key set exactly equals
   `ExperimentDefinition.allowed_change`.

Binding is structural only. It does not execute the experiment, instantiate or
mutate an authoritative StrategyConfig, bypass OOS/walk-forward validation, or
authorize execution.

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
