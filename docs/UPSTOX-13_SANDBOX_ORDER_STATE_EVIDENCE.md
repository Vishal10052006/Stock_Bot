# UPSTOX-13 — Sandbox Order-State Evidence Capture

## Scope

UPSTOX-13 adds a deterministic evidence-capture boundary for an already-observed sandbox order response sequence.

The capture function performs no network I/O. It only validates and records provider responses supplied by a controlled integration runner.

## Evidence semantics

A placement identity and subsequent broker lookup identity must match before the order-history capability can be recorded as VERIFIED.

A missing lookup remains UNVERIFIED.

A mismatched broker order identity, mismatched deterministic tag, or unsuccessful observed cancellation acknowledgement is FAILED.

The evidence is observational and never authorizes execution.

## Integration boundary

The existing sandbox integration test remains the opt-in network test. UPSTOX-13 does not change the default CI path and does not add credentials.

The current project evidence record states that full place to history to cancel remains uncertified because the installed SDK sandbox capability blocks the order-history resource. The new capture contract is therefore ready for a future provider-supported lookup mechanism without weakening reconciliation semantics.

## Safety

- Live broker execution remains LOCKED.
- No credentials are stored or logged.
- No order is submitted by the evidence-capture module.
- Sandbox observations are not promoted to production/live evidence.
