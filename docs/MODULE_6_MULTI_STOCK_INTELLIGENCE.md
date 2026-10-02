# Module 6 — Multi-stock Intelligence

## Status

**Foundation + PIT universe integration implemented.**

Module 6 aggregates validated per-stock AnalysisContext into a single causal
multi-stock observation and reuses the existing point-in-time Market Bot
universe infrastructure.

## Implemented

- deterministic universe canonicalization
- immutable multi-stock contracts
- AnalysisContext/object and mapping adapters
- coverage and availability accounting
- analytical direction/state aggregation
- future-context rejection
- duplicate-symbol rejection
- declared-universe enforcement
- provenance/version metadata
- PIT Market Bot universe integration
- observation-only authority
- regression tests

## Boundaries

Multi-stock intelligence does not create BUY/SELL decisions, position sizing,
risk approvals, execution authorization, or broker orders. Strategy, Risk,
Safety, and Execution remain downstream authorities.

## Next validation

Run the focused multi-stock tests, then the full repository suite and a
real-data/PIT integration check before declaring Module 6 complete.
