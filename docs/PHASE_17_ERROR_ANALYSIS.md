# Phase 17 — Error Analysis Engine

## Objective

Phase 17 turns Phase-16 trading memory into an observable error-analysis layer.

The roadmap asks the system to automatically surface patterns such as:

- losses concentrated in SIDEWAYS + RVOL < 0.8 + BREAKOUT;
- high-confidence false signals;
- performance observed during the opening 15 minutes;
- outcomes observed after two consecutive losses.

These are associations in the journal population, not causal claims.

## Inputs

Phase 17 consumes:

1. TradeDecisionRecord — the exact decision-time context.
2. TradeJournalRecord — the canonical completed trade outcome.

A decision participates in contextual pattern discovery only when its trade_id matches the completed outcome.

This prevents the analyzer from reconstructing decision context from future information.

## Analysis layers

### 1. Per-trade findings

The existing deterministic checks remain:

- LOSS
- WIN
- LARGE_MAE
- LOW_MFE
- COST_DRAG

### 2. Pattern discovery

PatternFinding reports:

- pattern type
- explicit condition set
- evidence count
- population count
- occurrence rate
- average net P&L of evidence
- total net P&L
- source trade IDs
- descriptive detail

Implemented pattern classes:

- REGIME_LOSS_CLUSTER
- LOW_RVOL_SIDEWAYS_BREAKOUT
- HIGH_CONFIDENCE_FALSE_SIGNAL
- OPENING_WINDOW_LOSS
- CONSECUTIVE_LOSS_STREAK

Patterns are emitted only when the configured minimum evidence and occurrence-rate thresholds are satisfied.

## Causality and safety

The analyzer does not:

- modify strategy rules;
- change Risk Engine limits;
- retrain a model;
- promote a model;
- authorize an order;
- infer that a condition caused a loss.

A finding means:

"This condition is associated with these observed outcomes in the analyzed journal population."

It does not mean:

"This condition caused the losses."

## Consecutive-loss definition

For the default configuration, an outcome is in the after_2_consecutive_losses population when the two immediately preceding completed outcomes were losses.

The implementation evaluates the sequence chronologically by entry_time.

## Opening-window definition

The default opening window is the first 15 minutes beginning at 09:15 in the timestamp's own timezone.

The threshold is configurable and does not assume that a timestamp is naive.

## Statistical guardrails

Default pattern discovery requires:

- at least 3 evidence trades;
- at least 50% occurrence rate within the condition population;
- high-confidence threshold of 0.70;
- low-RVOL threshold of 0.80.

These are evidence filters, not profitability criteria.

The analyzer intentionally does not perform automatic multiple-testing correction or claim statistical significance. Phase 17 is an evidence surfacing layer; later validation phases must determine whether a discovered pattern survives rigorous testing.

## Pipeline

    Phase 16 Decision Memory
              |
              v
       Decision + Outcome
              |
              v
       Phase 17 Analyzer
          /          \
         v            v
   Per-trade      Pattern discovery
   findings           |
         \            /
          v          v
         ErrorAnalysisReport
                  |
                  v
             Phase 18 Learning

Phase 18 may consume these observations as evidence. Phase 17 itself has no model-changing authority.

## Validation

Focused Phase-17 tests cover:

- regime loss clusters;
- low-RVOL sideways breakout losses;
- high-confidence false signals;
- opening-window losses;
- consecutive-loss streaks;
- exclusion of unlinked outcomes;
- deterministic repeated analysis.

Full repository regression remains required before Phase 17 is considered releasable.
