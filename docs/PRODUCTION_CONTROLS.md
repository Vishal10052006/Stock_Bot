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
