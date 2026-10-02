# Module 6 — Multi-stock Intelligence

## Status

**M00 Universe Manager + M01 Stock Ranking + M02 Sector Rotation + M03 Market Breadth + PIT causal validation implemented.**

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
- deterministic PIT adapter integration tests with in-memory Security Master/Bhavcopy fixtures
- future PIT universe rejection
- M01 deterministic stock ranking using existing AnalysisContext quality
- M02 point-in-time sector rotation snapshot from existing derived sector returns
- M02 ignores future sector context and preserves observation-only authority
- deterministic tie-breaking and explicit exclusion of unavailable quality

## Boundaries

Multi-stock intelligence does not create BUY/SELL decisions, position sizing,
risk approvals, execution authorization, or broker orders. Strategy, Risk,
Safety, and Execution remain downstream authorities.

## Next validation

Focused M00/M01 tests and the full-suite execution remain the final validation gate. The PIT
integration tests use deterministic in-memory adapters; no external NSE or
Upstox network call is performed by the test suite.

- M03 descriptive market breadth: advances, declines, unchanged, coverage, breadth ratio, and advance/decline ratio from causal stock returns
- M03 missing returns are excluded rather than inferred; future/duplicate observations fail closed

- M04 causal pairwise correlation matrix from historical return observations
- M04 deterministic symbol ordering, duplicate-row rejection, minimum-overlap validation, and no future-data usage
