# UPSTOX-17 — Process Restart / Recovery Evidence

## Scope
UPSTOX-17 adds a deterministic evidence boundary for process restart and execution-state rehydration.

## Evidence semantics
- Post-restart state must preserve client-order identity.
- Recovery must not increase broker submission count.
- A valid rehydrated state can be marked VERIFIED.
- Missing post-restart state remains UNVERIFIED.
- UNKNOWN remains UNVERIFIED until broker truth resolves it.
- Identity mismatch is FAILED.
- Invalid lifecycle states fail closed.

## Safety
This helper consumes already-observed state only. It performs no network I/O,
does not resubmit orders, and does not authorize execution.

The existing ExecutionEngine.rehydrate() remains the canonical broker-truth recovery mechanism.

## Provider limitation
Local/deterministic evidence does not establish that real Upstox sandbox process-restart behavior has been observed. Real-provider restart evidence remains UNVERIFIED until intentionally captured.
