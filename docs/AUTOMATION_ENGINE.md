# STOCK_BOT Automation Engine

The Automation Engine is the control plane for STOCK_BOT. It coordinates
existing engines and preserves their authority boundaries.

## Runtime graph

DATA → RESEARCH → MARKET → ANALYSIS → PREDICTION → STRATEGY → RISK →
SAFETY → EXECUTION → MONITORING

## Core invariants

1. Decision timestamps are timezone-aware.
2. Future observations are rejected.
3. Missing integration handlers are explicit skips.
4. Execution admission is restricted to PAPER mode.
5. Duplicate logical runs are rejected through deterministic idempotency.
6. Learning/promotion is not an execution authority.
7. Live broker execution remains independently fail-closed.

## AUTO-00 → AUTO-20

AUTO-00 through AUTO-20 are mapped to a single reusable automation control
plane instead of twenty duplicate implementations. Concrete engine logic remains
owned by the existing component packages.

## Production posture

The current repository supports automated real-market observation and paper
orchestration paths, but live broker execution remains locked until the existing
production-readiness and independent safety gates are satisfied.
