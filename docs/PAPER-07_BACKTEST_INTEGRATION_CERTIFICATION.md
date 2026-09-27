# PAPER-07 — E16 Backtest Integration Certification

## Purpose

Certify the boundary between historical backtesting and the canonical execution contract.

The existing backtest engine already follows:

Strategy → Candidate/Risk → ExecutionAuthorization → BrokerSimulator

The certification verifies that boundary rather than introducing a second execution engine.

## Certification matrix

| Case | Coverage |
|---|---|
| authorized_path_uses_canonical_boundary | Approved Risk authorization reaches the historical broker simulator |
| no_trade_stays_no_trade | Non-actionable strategy does not create an order |
| backtest_costs_match_execution_assumptions | Historical simulator assumptions match execution assumptions |
| assumption_mismatch_fails_closed | Cost/slippage mismatch is rejected |
| chronology_and_causality_are_preserved | Historical replay remains chronological and causal |
| risk_quantity_is_not_replaced_by_backtest_config | Risk-approved quantity remains authoritative |

## Safety boundary

Backtesting may simulate execution but does not bypass Risk or create live broker authority.

The historical broker simulator remains a thin adapter over the deterministic paper runtime. It reuses the existing fill, fee, position, and journal semantics rather than creating another accounting model.

## Live trading

No live broker is contacted by this certification. Upstox/live execution remains locked.

## Scope limitation

This certification covers the current E16 integration boundary. It does not claim that historical simulation is economically identical to real-market execution; market impact, queue position, latency, liquidity, and live broker behavior remain separate validation concerns.
