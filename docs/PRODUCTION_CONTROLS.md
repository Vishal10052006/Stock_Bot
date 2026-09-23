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
