# Phase 18 — Full Sandbox / Paper E2E Validation

The repository now has a deterministic end-to-end contract test covering the
chronological paper-session path:

`Market rows -> Strategy -> Risk -> ExecutionAuthorization -> PaperTradingRuntime -> Evidence`

The test also verifies that the resulting paper evidence does not grant broker
authority and that the Phase 25 locked gateway continues to reject broker state
access.

This is **local deterministic sandbox/paper validation**. It is not current
Upstox API verification, live broker certification, compliance approval, or
live-readiness evidence.
