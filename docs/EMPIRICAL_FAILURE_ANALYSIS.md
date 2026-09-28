# EMP-06 — Empirical Paper Failure Analysis

## Purpose

EMP-06 is the descriptive analysis boundary after EMP-05 evidence validation.

It answers:

- how many chronological decision steps produced strategy signals
- how many reached risk approval/rejection
- why signal decisions were rejected
- how many paper orders were generated and filled
- signal and fill distribution by symbol and regime
- the observed paper-runtime equity path and maximum drawdown
- which observations are deterministic paper observations versus external observations

It does **not**:

- optimize strategy thresholds
- rank strategies
- infer profitability from a single run
- manufacture missing trade outcomes
- authorize live execution
- promote a model

## Required input

A frozen strategy-ready parquet accepted by EMP-05.

The analyzer reruns that dataset through the authoritative PaperDecisionLoop; it does not reconstruct decisions from the evidence counters.

## Output

The JSON report records the dataset SHA-256, dataset version, run identity, risk-status distribution, rejection reasons, signal/fill distributions, and runtime equity summary.

The equity summary is based on the paper runtime's chronological account snapshots. It is a simulated paper-account observation and is not a broker statement.

## Interpretation boundary

EMP-05 EVIDENCE_VALIDATED means the evidence contract is satisfied for the supplied observations.

EMP-06 provides the descriptive failure/execution breakdown needed before deciding whether additional paper observations or a research investigation are warranted.

A low fill count is reported as observed. It is not automatically treated as a strategy defect; the rejection reasons must be inspected first.


## EMP-06.1 — Gross exposure diagnostics

For signals rejected by the frozen gross-exposure control, the analyzer records the
decision-time exposure before the proposed trade, the frozen exposure limit, the
hypothetical exposure after the proposed quantity, utilization before/after, excess
exposure, proposed notional, and rejection counts by symbol.

These observations are diagnostic only. They do not alter the 75% gross-exposure
policy and do not imply that the policy should be relaxed.

The exposure-after value for a rejected trade is hypothetical: no order was
submitted and no portfolio state was mutated by that rejected candidate.
