# Module 7 — Decision Explanation

## Status

**COMPLETE — authoritative explanation contract, audit gate, concrete pipeline integration, desktop integration, and regression coverage implemented.**

Module 7 is an observation/presentation layer. It explains already-produced pipeline evidence; it never creates or changes a trading decision.

## Scope

The explanation boundary consumes evidence from:

```
Market
  ↓
Analysis
  ↓
Prediction
  ↓
Research / Screen
  ↓
Strategy
  ↓
Risk
  ↓
Safety
  ↓
Execution
```

The order represents the canonical causal pipeline. Evidence may be omitted when unavailable; missing evidence is never replaced with an invented reason.

## Implemented

### 1. Authoritative explanation contract

`multi_stock/decision_explanation.py`

- `DecisionExplanationItem`
- `DecisionExplanation`
- `build_decision_explanation()`
- timezone-aware decision/evidence timestamps
- symbol canonicalization
- future-evidence rejection
- deterministic item ordering
- observation-only authority
- structured source attribution

### 2. Pipeline evidence

The builder can consume:

- market context
- analysis context
- prediction context
- research evidence
- Screen Observer evidence
- StrategyDecision
- RiskDecision
- SafetyDecision
- ExecutionAuthorization
- ExecutionResult / OrderSnapshot

### 3. Structured reasons

The explanation uses existing authoritative fields:

- Strategy: `primary_reason`, `secondary_reasons`, `rationale`
- Risk: `reason`
- Safety: `block`, `reason`
- Execution: `OrderSnapshot.reason`, then observed execution error

No explanation reason is fabricated.

### 4. Outcome states

Supported observed outcomes include:

- `NO_TRADE`
- `LONG`
- `SHORT`
- `RISK_REJECTED`
- `SAFETY_BLOCKED`
- `EXECUTION_BLOCKED`
- `EXECUTION_REJECTED`
- `EXECUTION_PENDING`
- `EXECUTION_FILLED`
- `OBSERVATION_ONLY`

Execution authorization is deliberately not treated as proof of a fill.

### 5. Outcome precedence

The explanation preserves upstream authority:

```
Strategy NO_TRADE
    ↓
Safety BLOCK
    ↓
Risk REJECT
    ↓
Execution lifecycle
    ↓
Strategy LONG/SHORT
```

A downstream execution block caused by a risk rejection does not overwrite the upstream risk explanation.

### 6. Explanation audit

`multi_stock/explanation_audit.py`

The audit gate verifies:

- observation-only authority
- expected symbol
- known explanation stages
- duplicate stages
- causal stage ordering
- outcome/state consistency
- required evidence for reported outcomes
- execution lifecycle consistency

Audit failure is fail-closed.

### 7. Desktop integration

`desktop/read_models.py::build_explanation()`

The desktop Explanation Panel consumes the authoritative Module 7 contract and audit result rather than maintaining a second explanation engine.

Invalid explanation evidence becomes desktop state `INVALID`.

### 8. Regression coverage

Module 7 tests cover:

- causal ordering
- future evidence
- symbol mismatch
- missing reasons
- strategy primary/secondary reasons
- risk rejection
- safety blocking
- execution lifecycle states
- execution authorization vs actual fill
- concrete production contract objects
- enum normalization
- explanation audit failures
- missing outcome evidence

## Authority boundaries

Module 7 does **not**:

- create BUY/SELL decisions;
- alter Strategy decisions;
- approve or reject Risk;
- operate the Safety Gate;
- submit/cancel broker orders;
- modify execution state;
- promote/retrain models;
- infer missing evidence.

Canonical trading authority remains:

```
Prediction
   ↓
Strategy
   ↓
Risk
   ↓
Safety
   ↓
Execution
```

Module 7 observes and explains that chain.

## Definition of Done

| Requirement | Status |
|---|---|
| Structured explanation contract | COMPLETE |
| Full pipeline evidence support | COMPLETE |
| Causal timestamp validation | COMPLETE |
| Symbol validation | COMPLETE |
| Structured reason extraction | COMPLETE |
| Execution lifecycle mapping | COMPLETE |
| Upstream rejection precedence | COMPLETE |
| Explanation audit gate | COMPLETE |
| Missing-evidence fail-closed behavior | COMPLETE |
| Desktop D03 integration | COMPLETE |
| Concrete production-contract tests | COMPLETE |
| Observation-only boundary | COMPLETE |
| No fabricated causes | COMPLETE |

## Validation

Focused Module 7 tests are located in:

- `tests/multi_stock/test_decision_explanation.py`
- `tests/multi_stock/test_explanation_audit.py`

The full repository regression suite should be run from the user's checkout before treating this branch as release-validated.

## Completion boundary

Module 7 is complete at the explanation-contract and integration level.

The next project module in the authoritative project sequence is:

**Module 8 — Empirical Learning Loop.**
