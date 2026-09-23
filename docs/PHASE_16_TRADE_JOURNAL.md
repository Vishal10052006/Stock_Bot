# Phase 16 — Trade Journal / Trading Memory

## Objective

Phase 16 makes trading memory a first-class, append-only evidence layer.

The roadmap requires every decision to preserve:

- trade_id
- timestamp
- symbol
- direction
- market_regime
- features
- model_version
- probability
- entry
- stop
- target
- position_size
- exit
- PnL
- MAE
- MFE
- holding_time
- result
- failure_reason

The implementation separates the decision snapshot from the completed outcome while linking them with the same deterministic trade_id.

## Contract

### Decision memory

TradeDecisionRecord stores the exact strategy-time context:

- causal timestamp and symbol
- LONG / SHORT / NO_TRADE decision
- market regime
- decision-time features
- prediction model version and probability
- entry / stop / target references
- Risk-approved position size when Risk has evaluated the decision
- strategy/risk/execution versions
- stable failure reason for NO_TRADE or rejected risk
- provenance

NO_TRADE is a first-class journal event. It is not silently discarded.

### Outcome memory

TradeJournalRecord stores the canonical completed TradeOutcome:

- entry/exit timestamps and prices
- quantity
- gross/net P&L
- fees and slippage
- holding time
- MAE / MFE
- linked trade_id

The existing learning and error-analysis modules continue to consume completed outcome records through TradeJournal.records().

## Persistence

TradeJournalStore uses append-only JSONL.

Each event has an explicit record_type:

- decision
- outcome

One decision and one outcome may share a trade_id. Duplicate events of the same type for the same trade are rejected.

Existing outcome-only journal files remain readable because missing record_type is treated as an outcome record.

## Causality and integrity

The journal does not infer missing trading evidence.

- Decision features are captured from StrategyDecision.features.
- Risk sizing is taken from RiskAssessment.position_size or execution authorization.
- Outcome values are taken from the canonical TradeOutcome.
- Deterministic SHA-256 identities make repeated identical decision snapshots reproducible.
- Non-finite numeric journal values are rejected.
- Timestamps must be timezone-aware.
- Decision and outcome records remain immutable dataclasses.

## Downstream learning boundary

Phase 16 is storage and memory, not automatic model adaptation.

The existing error-analysis and learning layers consume journal outcomes to identify observable patterns. They do not receive authority to bypass Risk or mutate a production model directly.

Pipeline:

    Strategy Decision
          |
          v
    TradeDecisionRecord
          |
          +------> Risk / Execution context
          |
          v
    Paper / Backtest Outcome
          |
          v
    TradeJournalRecord
          |
          v
    Error Analysis -> Learning Evidence

## Validation

Focused tests cover:

- complete decision-memory fields
- first-class NO_TRADE decisions
- linked decision/outcome records
- JSONL round-trip persistence
- deterministic trade identity
- rejection of non-finite feature values

Phase 16 does not authorize live broker execution.
