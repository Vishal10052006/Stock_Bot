# Phase 22 — Paper Trading

## Objective

Phase 22 is the empirical paper-trading boundary between deterministic research
validation and any later operational deployment work.

The phase has two separate states:

1. **Engineering implementation** — the paper runtime, decision loop, evidence
   contracts, journal, quality checks, and reproducible runner exist.
2. **Empirical completion** — actual chronological paper observations have been
   collected and satisfy the evidence contract.

Passing unit tests establishes the first state. It does not manufacture the
second.

## Authoritative flow

```
Market / Feature / Prediction Context
                |
                v
         Strategy Engine
                |
                v
           Risk Engine
                |
                v
    Execution Authorization
                |
                v
       Paper Trading Runtime
                |
                v
        Paper Evidence Journal
                |
                v
      Evidence Quality Report
```

No broker/network order is submitted.

## Empirical runner

The reproducible entry point is:

```bash
python scripts/trading/run_empirical_paper.py \
  --input data/paper/frozen_rows.parquet \
  --dataset-version paper-2026-09-v1 \
  --code-version <git-sha> \
  --evidence-version PAPER-EVIDENCE-v1 \
  --journal data/paper/paper_evidence.jsonl \
  --output data/paper/empirical_paper_report.json
```

The input must already be chronological. The runner deliberately refuses to
sort the dataset because reordering empirical observations can hide upstream
timestamp defects.

## Required decision-time fields

- timestamp
- symbol
- close
- regime
- regime_probability
- vwap_distance_pct
- rvol_20
- higher_high
- higher_low
- lower_low
- lower_high

## Evidence

The paper evidence contract records:

- signal observations;
- fills;
- slippage;
- fill latency;
- false-signal observations;
- equity/drawdown observations;
- regime observations;
- calibration observations;
- operational events/errors/stale events.

Observations that cannot be established by the deterministic paper loop must be
provided explicitly. The system does not invent latency, calibration, false
signals, equity, or operational measurements.

## Completion rule

Phase 22 must **not** be marked empirically complete merely because tests pass.

Empirical completion requires a real chronological paper run, persisted through
the append-only evidence journal, with the required evidence classes present and
structurally valid.

The evidence validator is deliberately non-evaluative: it does not decide
whether a strategy is profitable, superior, or suitable for live deployment.

## Safety boundary

Paper trading remains downstream of Risk and Execution Authorization.

```
Paper signal
   ↓
Risk approval
   ↓
Execution Authorization
   ↓
Paper Runtime

NO broker authority
NO live order submission
NO automatic model promotion
NO automatic strategy mutation
```
