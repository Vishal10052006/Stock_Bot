# CERT-08 — Paper Soak Runbook

CERT-08 uses only persisted virtual-paper session artifacts.

- No live broker orders are permitted.
- `live_broker_orders` must remain zero.
- Shorter runs remain PARTIAL.
- Multiple market-session directories can be aggregated; overnight time is not counted.

## Validate one session

    python scripts/validate_virtual_session.py paper/virtual_sessions/<session-id>

## Aggregate one or more sessions

    python scripts/cert08_paper_soak.py paper/virtual_sessions/<session-id> --required-hours 6 --output paper/soak_evidence/<session-id>.json

For multiple sessions:

    python scripts/cert08_paper_soak.py paper/virtual_sessions/<session-a> paper/virtual_sessions/<session-b> --required-hours 12 --max-gap-minutes 10 --output paper/soak_evidence/CERT08-campaign.json

The optional `--max-gap-minutes` records large observation gaps as a cadence violation; such evidence remains PARTIAL.

The harness never manufactures timestamps, fills, latency, calibration, false-signal outcomes, or operational events.

CERT-08 may become PASS only from persisted, validated paper evidence whose aggregate observed market-session duration satisfies the configured requirement.
