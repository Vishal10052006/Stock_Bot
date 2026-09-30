# STOCK_BOT — Monitoring M-20..M-24 Completion

## Scope

M-1 through M-19 are already implemented as the Monitoring Engine. The remaining
work is **empirical completion evidence**, not another monitoring subsystem.

This document closes that remaining boundary as five evidence gates:

| Gate | Purpose |
|---|---|
| M-20 | Empirical evidence identity and validation status |
| M-21 | Chronological run identity and observation accounting |
| M-22 | Cross-layer monitoring coverage and counter consistency |
| M-23 | Failure/calibration semantics without fabricated observations |
| M-24 | Operational observability and final monitoring completion gate |

## Architectural boundary

Monitoring remains observational:

`Market / Analysis / Model / Strategy / Risk / Execution
→ MonitoringRuntime → MonitoringEngine → Metrics / Alerts / Dashboard / Journal`

It must not:

- authorize or reject trades;
- size positions;
- mutate strategy/model/risk configuration;
- submit broker orders;
- promote models;
- manufacture missing outcomes.

## Completion rule

Run:

`PYTHONPATH="$PWD" python3 scripts/trading/validate_monitoring_completion.py
`

The default input is:

`data/paper/empirical_paper_report_v3.json`

A successful result means the monitoring **evidence/completion contract** passed.
It does **not** mean profitable, live-ready, or predictive.

### Important evidence semantics

- A deterministic baseline can legitimately have zero calibration observations because
  it emits no probabilities.
- A zero false-signal count means the outcome was not observed; it is not a claim
  that there were no false signals.
- Staleness is measured explicitly.
- Chronological evidence must originate from the authoritative paper run; this validator
  checks the resulting report's accounting rather than reconstructing missing timestamps.
- Risk/exposure findings remain diagnostics. They do not silently alter the frozen
  0.5% risk/trade or 75% gross-exposure baseline.

## Current empirical evidence boundary

The existing EMP-05/EMP-06 run provides real chronological paper observations and
failure-analysis evidence. This completion gate formalizes the final monitoring
validation around those observations.

The final project interpretation remains:

**Monitoring implementation: COMPLETE.**  
**Empirical monitoring evidence: COMPLETE only when the completion command returns PASS.**  
**Live trading: NOT AUTHORIZED by this monitoring gate.**
