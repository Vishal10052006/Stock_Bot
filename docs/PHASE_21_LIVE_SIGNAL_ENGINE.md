# STOCK_BOT — Phase 21 Live Signal Engine

**Status:** IMPLEMENTED — BROKER-FREE SIGNAL BOUNDARY

## Objective

Phase 21 composes the existing decision authorities into one immutable,
auditable live signal:

Market snapshot → Strategy → Risk → LiveSignal

The engine does **not** place orders, contact a broker, mutate strategy/risk
configuration, promote a model, or enable live execution.

## Existing authorities reused

- StrategyEngine remains the quantitative decision authority.
- RiskEngine remains the hard-veto and risk-first sizing authority.
- trading.strategy.candidate_adapter remains the causal Strategy → TradeCandidate boundary.
- Existing prediction/analysis contexts are passed through StrategyInput.
- Existing execution authorization and Paper Trading remain downstream.

## Signal identity

LiveSignal.signal_id is a deterministic SHA-256 identity derived from:

- decision timestamp;
- symbol;
- strategy version;
- prediction model version;
- feature version;
- risk version.

Repeated evaluation of the same decision-time state therefore produces the
same signal identity.

## Freshness and causality

The engine requires timezone-aware decision timestamps and rejects future
timestamps. A configurable freshness policy defaults to 30 seconds.

A stale or future event is converted to an auditable NO_TRADE signal rather
than being allowed into the Strategy/Risk pipeline.

## Independent health boundary

Phase 21 fails closed before Strategy evaluation when:

- the supplied system is not ready;
- market data is invalid/unavailable;
- the kill switch is active.

The same portfolio/risk state is then supplied explicitly to the existing
Risk boundary. No hidden account state is introduced.

## Decision behavior

1. Validate the Phase-21 input contract.
2. Validate timestamp freshness and future-event constraints.
3. Validate independent system-health boundaries.
4. Construct the existing StrategyInput.
5. Run the authoritative StrategyEngine.
6. Run the existing Strategy → TradeCandidate → Risk pipeline.
7. Produce ACTIONABLE only when Strategy is directional and Risk is APPROVED
   with a positive risk-derived position size.
8. Otherwise produce NO_TRADE with an explicit reason.
9. Return the immutable signal with strategy/risk/provenance information.

## Safety boundary

Phase 21 has no broker client and no execution call.

The resulting LiveSignal is the intended input boundary for Phase 22 Paper
Trading. Execution authorization remains downstream.

## Files

- live_signal/models.py — immutable signal/input contracts.
- live_signal/risk_state.py — explicit decision-time portfolio state.
- live_signal/engine.py — Strategy → Risk orchestration.
- tests/live_signal/test_engine.py — contract, freshness, health, strategy,
  risk, deterministic-identity and failure-path tests.

## Definition of Done

- [x] Immutable LiveSignal contract
- [x] Deterministic signal identity
- [x] Explicit ACTIONABLE / NO_TRADE status
- [x] Strategy and Risk provenance
- [x] Freshness/future-event validation
- [x] Independent health fail-closed boundary
- [x] Broker-free implementation
- [x] Unit/integration-style regression tests added
- [x] Full repository test run after integration — current `main` contains the integrated Phase-21 boundary and the repository CI/evidence records remain green; the outstanding local gate is the real chronological observation run
- [ ] Live chronological observation run

## Next phase

Phase 22 consumes LiveSignal and records paper orders/fills, positions, P&L,
and journal evidence. Phase 21 itself does not establish profitability or live
readiness.