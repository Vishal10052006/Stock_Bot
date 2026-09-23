# STOCK BOT — Remaining Production Controls

| Requirement | Repository status |
|---|---|
| Independent kill switch | Implemented |
| Safety/data/session gate | Implemented |
| Broker position reconciliation contract | Implemented |
| Live-readiness gate | Implemented |
| Live broker connectivity | Intentionally locked / not enabled |
| Current broker/exchange verification | External evidence required |
| Current regulatory verification | External evidence required |

## Architecture

```
Strategy
   ↓
Risk
   ↓
Execution Authorization
   ↓
Independent Safety Gate
   ↓
[Live lock / broker adapter]
   ↓
Broker
   ↓
Reconciliation
   ↓
Monitoring / Journal
```

The independent safety layer is separate from model/strategy output. A kill
switch, stale-data state, invalid data-quality state, or closed session blocks
execution.

The reconciliation layer compares local and broker position snapshots and
reports mismatches. It intentionally does not invent broker state.

The live-readiness gate maps directly to the validation gates in
`TRADING_SPECIFICATION.md §26`. It is fail-closed: every required gate must
be explicitly supplied as true.

## Live lock

The repository remains locked for live financial execution.

A readiness report of `ready=True` is only a structural checklist result.
It does not itself enable a broker connection or place an order.

Current broker credentials, broker-specific order semantics, exchange rules,
and regulatory requirements must be verified separately and kept as dated
evidence before any future activation.


## Paper-evidence boundary

`experiments.paper_evidence` provides a structural evidence contract for the
paper-trading requirements in `TRADING_SPECIFICATION.md §24`. A frozen evidence
snapshot records counts for signals, fills, slippage, latency, false signals,
drawdown, regime behavior, calibration, and operational events, together with
dataset/code identity.

The validator checks completeness and internal count consistency. It deliberately
does not apply a profitability threshold, rank strategies, or convert paper
results into live authorization. Paper evidence remains one input to the separate
live-readiness checklist.

The `PaperEvidenceCollector` and `collect_paper_decision_run` adapter can derive signal, fill, slippage, and regime observations directly from a chronological paper decision run. Latency, false-signal outcomes, equity observations, and calibration outcomes remain explicit inputs because they cannot be inferred safely without additional timestamps/outcomes. This prevents synthetic evidence from being created by the reporting layer.


## Persistent paper-evidence journal

`experiments.paper_journal` adds a deterministic, append-only JSONL boundary for
paper-evidence records. A record binds the frozen evidence fingerprint to its
paper period, source run identity, and record version; its `run_id` is derived
from those immutable inputs.

`PaperEvidenceJournal` never rewrites existing records. Duplicate run identities
are rejected, and every loaded line is reconstructed through the immutable
record contract so a tampered period, source identity, or evidence payload is
detected instead of being silently accepted.

The journal provides reproducibility and auditability only. It does not infer
missing observations, alter evidence, rank paper runs, or authorize live
execution.

## Paper run identity boundary

`PaperDecisionRun.run_id` now provides a deterministic identity derived from the completed strategy, risk, authorization, and paper-order outputs. `PaperDecisionLoop.run_and_persist_evidence(...)` uses that identity automatically as the journal record's `source_run_id`, so evidence cannot be accidentally attached to an unrelated manually supplied run label.

`run_and_persist_evidence` still requires explicit observations that the decision loop cannot establish causally on its own, including fill timestamps, false-signal outcomes, equity observations, calibration outcomes, and operational counts. The convenience boundary therefore reduces identity ambiguity without manufacturing evidence.

## Aggregate paper-evidence quality

`experiments.paper_quality.assess_paper_evidence(...)` aggregates persisted journal records into a structural quality report. It reports record validity, observation counts, dataset/code/evidence versions, and validation issues across the supplied period.

The report is intentionally not a performance evaluator: it does not rank paper runs, calculate profitability, infer missing observations, or authorize live execution. An empty journal is not considered sufficient evidence, and any structurally invalid supplied record is surfaced explicitly.

## Paper evidence → live-readiness boundary

`LiveReadinessGate.evaluate(...)` can now accept a `PaperEvidenceQualityReport`. When supplied, an invalid or empty quality report adds the explicit `paper_evidence_quality_validated` failure gate. This connects structural paper-evidence quality to readiness without treating paper quality as a profitability judgment.

The existing `paper_evidence_validated` gate remains an explicit caller-supplied gate. The quality report is an additional evidence-integrity check; passing it does not enable live execution and does not replace OOS, walk-forward, risk, broker, reconciliation, or current compliance evidence.
