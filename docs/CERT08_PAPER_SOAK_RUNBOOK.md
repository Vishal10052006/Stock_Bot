# CERT-08 — Paper Soak Runbook

This runbook describes how to collect real long-duration paper-soak evidence for
the production-readiness gate.

## Safety boundary

The CERT-08 soak uses the existing virtual/paper execution path only.

- No live broker orders are permitted.
- The virtual-session validator requires `live_broker_orders == 0`.
- CERT-08 is PASS only when the persisted session covers the configured
  required duration and the underlying virtual-session validator passes.
- A shorter but structurally valid run is recorded as PARTIAL, never upgraded.

## Procedure

1. Start the existing virtual paper session using the repository's normal
   paper/virtual-session entry point.
2. Keep the session running for the required operational soak window selected
   for this certification.
3. Preserve the resulting
   `paper/virtual_sessions/<session-id>/account_ledger.jsonl` and
   `account_summary.json`.
4. Validate the persisted session:

```bash
python scripts/validate_virtual_session.py \
  paper/virtual_sessions/<session-id>
```

5. Produce the CERT-08 evidence artifact:

```bash
python scripts/cert08_paper_soak.py \
  paper/virtual_sessions/<session-id> \
  --required-hours <required-hours> \
  --output paper/soak_evidence/<session-id>.json
```

## Evidence requirements

The emitted artifact records:

- session identity;
- observed start/end timestamps;
- observed duration;
- required duration;
- ledger row count;
- completed trades;
- final equity and realized P&L;
- live broker order count;
- validator status;
- deterministic evidence fingerprint.

The harness does not infer missing timestamps, fills, latency, calibration,
false-signal outcomes, or operational events. Those remain governed by the
existing paper-evidence contracts.

## Certification rule

CERT-08 may be changed from PARTIAL to PASS only from the persisted,
validated artifact produced by an actual run whose observed duration meets the
configured requirement. Software tests alone do not satisfy the duration
requirement.
