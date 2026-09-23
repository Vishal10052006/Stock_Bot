# STOCK BOT — Phase 19 Candidate Improvement Engine

**Status:** COMPLETE — CONTROLLED RESEARCH PROPOSALS  
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


## Phase-19 execution invariant

A candidate must not merely be described as an experiment change; the bound experiment execution path must receive the candidate's materialized strategy configuration. The implementation therefore:

1. binds the candidate to the exact frozen `ExperimentDefinition`;
2. verifies the candidate's baseline strategy fingerprint;
3. materializes a new immutable `StrategyConfig` from the baseline plus the whitelisted candidate changes;
4. passes that research-only config to the experiment executor;
5. runs the result through `ExperimentRunner`, which verifies the returned `ExperimentRecord` belongs to the same frozen definition.

The authoritative baseline object is never mutated, and Phase 19 does not modify Risk, Execution, model registry state, or live enablement.

## Verification checkpoint — 2026-09-24

The Phase-19 audit added explicit regression coverage for:

- all 11 whitelisted StrategyConfig fields being materialized without mutating the authoritative baseline;
- rejection of Risk, Execution, Safety, and model-weight change surfaces;
- deterministic StrategyConfig, candidate, and binding fingerprints;
- candidate lineage back to the exact LearningExperience and source trade IDs;
- candidate-to-experiment and experiment-record identity checks;
- malformed or forbidden direct CandidateExperimentBinding construction;
- the candidate execution boundary exposing StrategyConfig only, with no RiskDecision or ExecutionAuthorization input;
- validation/execution leaving candidate status at PROPOSED.

A repository regression was also found outside Phase 19: the main branch contained
Prediction Bot inference/tests that referenced ml.prediction.contracts and
ml.prediction.storage while those files had not yet landed on main. The
missing Prediction Bot modules were restored from the existing completed
Prediction branch rather than reimplementing different contracts. This was a
regression-repair dependency required for a clean repository CI gate.

Phase 19 remains research-only. No candidate path reaches order authorization,
broker execution, live enablement, or automatic promotion.

## Final completion gate

Verified on 2026-09-24 against main commit `ebeea11deee57ff2853a290534ea87a2cf5de530`.

- Phase-19 dedicated tests pass.
- Market Bot regression pass.
- Phase-9 contract validation pass.
- Full repository regression pass in GitHub Actions run #416.
- Candidate changes are materialized into a new research-only `StrategyConfig`.
- The authoritative baseline remains fingerprint-stable and unmutated.
- Candidate, learning evidence, experiment definition, baseline strategy, and experiment record identities are explicitly bound and validated.
- Risk, Safety, Execution, broker, and live-enable controls remain outside the Phase-19 boundary.
- Candidate validation/execution does not promote or enable the candidate.
