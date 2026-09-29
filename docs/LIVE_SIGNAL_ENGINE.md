# STOCK_BOT — Phase 21 Live Signal Engine

## Purpose

The Live Signal Engine is the decision-time signal boundary between validated
market/feature/model context and the downstream Risk boundary.

It:

- consumes one StrategyInput at a time;
- enforces timezone-aware timestamps;
- rejects future observations;
- rejects stale decision inputs;
- enforces the frozen NSE 09:15–15:30 IST strategy session;
- rejects duplicate and out-of-order observations per symbol;
- delegates quantitative decision logic to the canonical StrategyEngine;
- preserves NO_TRADE as a first-class outcome;
- emits deterministic, immutable signal events.

## Authority boundary

The flow is:

    Validated decision-time context
              |
              v
       LiveSignalEngine
              |
              v
        StrategyEngine
              |
              v
       SIGNAL / NO_TRADE
              |
              v
          Risk Engine
              |
              v
    Execution Authorization
              |
              v
      Execution Engine

The Live Signal Engine does not:

- size positions;
- override Risk;
- create execution authorization;
- call a broker;
- submit orders;
- change model/strategy configuration;
- enable live trading.

A SIGNAL therefore means only that the canonical Strategy Engine produced an
actionable direction from an accepted decision-time input.

## Causality and chronology

observed_at is an explicit input rather than an implicit system clock. This
makes stale/future checks reproducible in tests and paper runs.

Per symbol, accepted timestamps must be strictly increasing. A duplicate or
out-of-order observation is blocked and does not advance the engine chronology.

## Session policy

The initial trading specification is NSE equity cash, intraday, 09:15–15:30 IST.
The engine normalizes timestamps to Asia/Kolkata before applying the session
boundary.

## Versioning

- Engine version: LIVE-SIGNAL-v1.0
- Strategy version remains owned by StrategyEngine.
- No model or strategy promotion occurs in this boundary.

## Safety position

This is a signal-generation component, not a live broker component. Live trading
remains locked by the system specification and execution readiness controls.
