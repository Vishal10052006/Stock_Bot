# Execution Engine Certification Report

## Scope

This report records the software-side certification checkpoint for the execution
boundary on branch `feat/execution-engine-completion`.

## Certified controls

- Risk-authorized immutable order requests
- Strict order lifecycle state machine
- Entry and explicit exit lifecycle
- Partial-fill handling
- Broker rejection handling
- UNKNOWN fail-closed state
- Broker-truth recovery and restart rehydration
- Deterministic client-order idempotency
- Signed long/short position reconciliation
- Independent kill-switch validation
- Execution monitoring and operational metrics
- Deterministic paper-soak execution
- Backtest/execution cost-assumption parity
- Bounded retry/backoff policy
- Timeout/network-failure validation
- Duplicate replay validation
- Operational runbook validation
- Fail-closed production readiness gate

## CI evidence

Validated commit:

`0d56ee6a941c7639e868845fef3afc2d9fd96d89`

CI results:

- Execution Validation — PASS
- Backtesting Validation — PASS
- Market Bot Validation — PASS

## External evidence boundary

The software certification above does not claim successful live-broker or
real-sandbox trading.

Upstox sandbox lifecycle validation remains an opt-in external test requiring a
valid sandbox access token, valid sandbox instrument token, price, and explicit
confirmation. Previous attempts using placeholder credentials produced HTTP 401
authentication failures; those runs are not evidence of a successful lifecycle.

The official SDK-backed sandbox client remains the preferred provider-evidence
path. Position reconciliation is not claimed from the sandbox because the
current sandbox capability surface does not provide the required position
evidence.

## Safety boundary

Live broker execution remains disabled. No certification step in this report
enables live trading.

## Operational conclusion

The execution engine's software-side implementation and hardening controls are
complete for this phase. Remaining work is external provider evidence and any
future broker-specific certification required before enabling a live environment.
