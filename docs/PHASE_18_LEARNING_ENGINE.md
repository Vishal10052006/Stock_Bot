# STOCK BOT — Phase 18 Learning Engine

**Status:** IMPLEMENTED AS CONTROLLED LEARNING EVIDENCE  
**Module:** `learning/engine.py`  
**Inputs:** Phase-16 trade outcomes + Phase-17 error analysis

## Objective

Phase 18 converts repeated observed trading outcomes into structured learning evidence.

The intended chain is:

```
Trade
  ↓
Outcome
  ↓
Error classification / pattern discovery
  ↓
Learning Experience
  ↓
Candidate Improvement
  ↓
Validation
```

The Learning Engine is **not** an automatic self-modification mechanism.

## Implemented

The learning layer consumes:

- per-trade LOSS/WIN findings;
- LARGE_MAE;
- LOW_MFE;
- COST_DRAG;
- Phase-17 pattern findings.

Phase-17 pattern experiences preserve:

- pattern type;
- explicit conditions;
- evidence count;
- population count;
- occurrence rate;
- deterministic evidence confidence;
- source trade IDs;
- average observed net P&L;
- total observed net P&L;
- descriptive detail.

Only source trade IDs present in the supplied learning population are retained.

## Safety boundary

The Learning Engine does not:

- modify model weights;
- retrain a production model;
- modify StrategyEngine rules;
- modify RiskEngine controls;
- promote a model;
- authorize execution;
- enable live trading.

The output is immutable evidence.

## Important distinction

The confidence value in a `LearningExperience` is an evidence-strength heuristic based on occurrence rate and evidence volume.

It is **not**:

- model probability;
- statistical significance;
- profitability probability;
- causal confidence.

Real learning conclusions require appropriate statistical validation.

## Existing generic reinforcement code

The repository still contains an older generic reinforcement implementation.

It remains outside the trading execution path and must not be interpreted as a market-outcome learning authority.

The controlled trading-learning path is:

```
Phase 16 Journal
      ↓
Phase 17 Error Analysis
      ↓
Phase 18 Learning Evidence
      ↓
Phase 19 Candidate Improvement
      ↓
Backtest / OOS / Walk-forward / Paper
```

No automatic promotion occurs.
