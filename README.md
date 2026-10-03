# STOCK_BOT

Personal-use, real-market trading decision-support system.

STOCK_BOT is being built for my own trading workflow, not as a SaaS product, broker-execution service, or multi-user trading platform. The system produces evidence-backed market decisions; the human operator performs the actual BUY/SELL action.

## Pipeline

Research → Analysis → Market → Prediction → Strategy → Risk → Execution → Monitoring → Learning

The system is designed around causal decision-time data, explicit risk authority, broker-neutral execution boundaries, controlled model evolution, and auditable manual outcomes.

## V1 real-money workflow

Real Market → Research → Analysis → Prediction → Strategy → Risk → Human Review → Manual BUY/SELL

The current V1 execution boundary is:

- real market data is authoritative for market context;
- live account/portfolio state is required for actionable manual review;
- Risk can fail closed when required context is missing, stale, or invalid;
- the dashboard presents the canonical decision for human review;
- ACCEPT never submits a broker order;
- the human operator remains the execution authority;
- manual outcomes are recorded as evidence for later analysis and learning.

The legacy paper/virtual-account runtime remains validation infrastructure. It is not the V1 real-money decision authority.

## Operator surfaces

### V1 Human Review Dashboard

dashboard.server is the local real-money manual-review surface:

- dashboard/index.html — local operator UI
- docs/V1_MANUAL_REVIEW_DASHBOARD.md — runtime/API/safety boundary
- journal/manual_review.py — append-only review/outcome evidence

Run it with explicit snapshot and journal paths:

    python -m dashboard.server \
      --snapshot-path <operator_snapshot.json> \
      --journal-path <manual_review.jsonl>

The server is loopback-only and does not expose broker order operations.

### Legacy Ops Center

dashboard/index.html also contains the earlier observational/demo Ops Center views and dashboard/demo_snapshot.json remains a synthetic visual fixture. These fixtures must not be interpreted as live account state or real trading evidence.

## Personal-use boundary

This repository intentionally does not optimize for:

- multi-user accounts;
- SaaS tenancy;
- public trading APIs;
- automatic broker execution;
- unattended autonomous BUY/SELL;
- using synthetic account state as live portfolio state.

The priority is correctness, causal data alignment, risk controls, observability, manual execution evidence, and safe personal use.

## Historical-data dependency

Point-in-time sector membership remains an external evidence dependency tracked in Issue #7. Historical constituent membership must come from an authoritative historical source; the project does not reconstruct missing historical membership from today's constituent lists.

## Development

Use the repository's Python environment and run focused tests plus the full regression suite before merging changes. For live-review changes, verify that the manual-review boundary remains broker-free and that no synthetic account or market context is introduced.