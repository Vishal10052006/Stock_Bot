# Empirical Paper Run

## Purpose

EMP-01 is the reproducible execution boundary for collecting actual paper-trading evidence from a frozen chronological strategy-ready dataset.

It is an evidence collection command, not a profitability test and not a live-readiness decision.

## Input contract

The parquet input must contain:

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

Rows must already be chronological. The runner deliberately refuses to reorder them because reordering an empirical dataset can hide an upstream timestamp problem.

## Evidence boundary

The runner delegates execution to the authoritative PaperDecisionLoop.

The loop can establish:

- strategy decisions;
- paper fills/orders;
- paper slippage;
- regime observations.

Additional observations that the loop cannot establish causally are supplied explicitly through an optional JSON sidecar:

- fill timestamps;
- false-signal outcomes;
- equity observations;
- calibration outcomes;
- operational event/error/stale counts.

No missing observation is synthesized.

## Command

```bash
python scripts/trading/run_empirical_paper.py \
  --input data/paper/frozen_rows.parquet \
  --dataset-version paper-2026-09-v1 \
  --code-version <git-sha> \
  --evidence-version PAPER-EVIDENCE-v1 \
  --journal data/paper/paper_evidence.jsonl \
  --output data/paper/empirical_paper_report.json
```

Optional external observations:

```bash
python scripts/trading/run_empirical_paper.py \
  --input data/paper/frozen_rows.parquet \
  --dataset-version paper-2026-09-v1 \
  --code-version <git-sha> \
  --evidence-version PAPER-EVIDENCE-v1 \
  --observations-json data/paper/evidence_observations.json \
  --journal data/paper/paper_evidence.jsonl \
  --output data/paper/empirical_paper_report.json
```

The evidence quality report may remain incomplete when the supplied period does not contain all required observation classes. That is intentional: structural completeness must be earned by actual observations.

## Output

The report binds:

- input period and symbols;
- deterministic PaperDecisionRun.run_id;
- evidence record identity/fingerprint;
- dataset version;
- code version;
- evidence version;
- aggregate paper-evidence quality.

It does not state that the strategy is profitable, superior, or ready for live trading.


## Automatic paper-runtime observations

The authoritative paper loop now records its own chronological account-equity observation for every decision step. When no external fill timestamps are supplied, deterministic paper fills use the simulated paper-order timestamp as the fill timestamp. This makes paper latency coverage explicit and auditable, but it is not broker/network latency.

The evidence runner also records one operational observation per completed decision step unless an explicit operational-event count is supplied through the sidecar.

These observations are generated from the paper runtime itself; they are not synthetic market outcomes.

### Calibration boundary

Calibration remains conditional on prediction output. The current deterministic baseline strategy does not emit prediction_probability, so calibration coverage is reported as not applicable rather than being fabricated. Once Prediction Bot supplies prediction probabilities and corresponding outcomes, the same evidence contract can record calibration observations through the sidecar.
