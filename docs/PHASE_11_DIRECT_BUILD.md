# STOCK_BOT — Phase 11 Direct Build

Risk Engine build is anchored to the existing Strategy -> Risk -> Execution
architecture.

## Implementation completed

The Risk Engine now provides:

- risk-first position sizing;
- direction-aware stop validation;
- deterministic 1.5R target construction;
- daily-loss protection;
- entries/day protection;
- open-position protection;
- gross-exposure protection;
- liquidity protection;
- duplicate-symbol protection;
- independent kill-switch state;
- machine-readable reason codes;
- immutable risk assessments;
- optional symbol/sector concentration;
- optional correlation concentration;
- optional volatility-aware sizing;
- explicit APPROVE / RESIZE / REJECT action semantics.

The existing causal Structure + ATR stop construction in
trading/signals/candidate.py remains authoritative. Risk validates and sizes
the candidate; it does not duplicate causal stop construction.

## Internal implementation sequence

11.2 Stop validation/hardening — COMPLETE
11.3 Target engine — COMPLETE
11.4 Position-sizing constraints — COMPLETE
11.5 Exposure controls — COMPLETE
11.6 Concentration/correlation — COMPLETE as opt-in controls
11.7 Daily limits/drawdown — COMPLETE for frozen daily-loss policy
11.8 Volatility adjustment — COMPLETE as opt-in control
11.9 Kill switch — COMPLETE
11.10 Unified Risk Decision Engine — COMPLETE
11.11 Integration boundary — COMPLETE through existing Strategy -> Candidate -> Risk path
11.12 Full validation — TESTS ADDED; repository-wide test execution must be run in the project environment

## Policy boundary

The current Trading Specification does not freeze numeric symbol, sector,
correlation, or volatility thresholds. Those controls therefore remain
disabled by default rather than inventing unvalidated production limits.

The frozen v1 policy keeps gross-exposure violations as hard NO_TRADE
conditions. Explicit allow_resize=True enables deterministic resizing for
advanced research experiments.

## Next implementation phase

Phase 12 — Backtesting Engine.

Risk remains the authority immediately upstream of execution and cannot be
overridden by Strategy or ML output.
