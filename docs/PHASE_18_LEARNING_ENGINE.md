# Phase 18 — Learning Engine

## Objective

Phase 18 redesigns trading learning around actual completed trading outcomes.

Required flow:

    Trade
      ↓
    Outcome
      ↓
    Reward
      ↓
    Error classification
      ↓
    Pattern discovery
      ↓
    Learning experience

The Phase-16 journal is the source of completed trade truth. Phase 17 supplies observable error and contextual pattern evidence.

## Reward contract

The reward is derived from realized net P&L.

When the decision contains entry and stop, planned monetary risk is:

    abs(entry - stop) * quantity

and normalized reward is:

    net_pnl / planned_risk

The reward is clipped to a configured bound (default ±3R) to prevent a single extreme trade from dominating the evidence layer.

If planned stop information is unavailable, the outcome entry notional is used as a conservative normalization denominator.

This reward is an evidence representation. It is not an optimization objective and does not authorize a model update.

## Error classification

Learning experiences classify observations into:

- OUTCOME_LOSS
- LARGE_ADVERSE_EXCURSION
- LOW_FAVORABLE_EXCURSION
- EXECUTION_COST_DRAG
- CONTEXT_LOSS_CLUSTER
- HIGH_CONFIDENCE_FAILURE
- SEQUENCE_DETERIORATION

## Evidence requirements

Default learning evidence requires:

- at least 3 trades;
- at least 50% occurrence within the relevant population;
- finite normalized rewards;
- deterministic source trade IDs.

Contextual error experiences must also have materially negative average reward under the configured threshold.

## Reinforcement redesign

The legacy generic predicted-vs-actual reinforcement calculation is no longer the trading learning authority.

learning/reinforcement_engine.py is now an evidence-only compatibility facade over actual TradeJournalRecord outcomes.

It:

- computes outcome-based reward;
- returns feedback data;
- cannot mutate model weights.

Attempting to use update_weights() raises an explicit error.

## What Phase 18 does NOT do

Phase 18 does not:

- retrain models;
- change strategy rules;
- modify Risk Engine limits;
- promote models;
- change production parameters;
- authorize orders.

A learning experience is evidence for a future controlled improvement process.

## Pipeline boundary

    Phase 16 Trade Memory
             ↓
    Phase 17 Error Analysis
             ↓
    Phase 18 Learning Engine
             ↓
    Learning Experiences
             ↓
    Phase 19 Candidate Improvement
             ↓
    Backtest → OOS → Walk-forward → Paper
             ↓
    Later model approval

This separation prevents a single losing trade from directly changing production behavior.


Validation status: pending CI on the final Phase-18 head.
