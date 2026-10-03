# V1 Human Review Dashboard Runtime

The V1 dashboard is now a local operator surface for the canonical manual-review boundary.

## Runtime

Start the dashboard with explicit runtime paths:

    python -m dashboard.server \
      --snapshot-path <operator_snapshot.json> \
      --journal-path <manual_review.jsonl>

The server defaults to a loopback bind address. It does not expose a broker API.

## API

### GET /api/snapshot

Returns the latest authoritative operator snapshot. The snapshot path is supplied by the operator at startup; the server does not invent account or market state.

### POST /api/review

Records an explicit human review:

    {
      "action": "ACCEPT",
      "reviewed_at": "2026-10-03T10:00:00+05:30",
      "review_note": "Reviewed the evidence chain."
    }

ACCEPT is rejected when the canonical signal is already expired. ACCEPT still does not execute a trade.

### GET /api/reviews

Returns the append-only manual review and outcome evidence currently stored by the configured journal.

### POST /api/outcome

Records only operator-supplied execution/outcome observations. The server requires an existing review and binds the outcome to that review's signal ID.

An EXECUTED or CLOSED outcome must contain the explicit execution facts required by ManualOutcomeRecord. A CLOSED outcome additionally requires exit facts and net P&L.

## Safety boundary

The dashboard server:

- never imports a broker client;
- never submits, modifies, cancels, or exits an order;
- never converts ACCEPT into an execution;
- never infers fills or P&L;
- rejects accepting an expired canonical signal;
- enforces one manual outcome per review;
- revalidates snapshot payloads through V1SignalContract.from_dict() before recording a review.

The human operator remains the execution authority.