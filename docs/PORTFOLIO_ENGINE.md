# STOCK_BOT — Portfolio Engine

## Scope

The Portfolio Engine is the aggregate portfolio-state boundary between Strategy
and Risk:

    Strategy
       ↓
    Portfolio
       ↓
    Risk
       ↓
    Safety
       ↓
    Execution

It evaluates the projected portfolio after a proposed trade. It does not:

- calculate risk-first position sizing;
- replace RiskEngine;
- create ExecutionAuthorization;
- contact a broker;
- submit orders;
- modify strategy/model configuration;
- enable live execution.

## Implemented

PortfolioSnapshot contains a decision-time timestamp, equity, and immutable
signed positions. Positive quantity is long and negative quantity is short.

TradeIntent contains symbol, positive proposed quantity, decision-time price,
BUY/SELL side, optional sector, and optional decision identifier. The quantity
is an input to the portfolio check only; PortfolioManager does not increase or
optimize it.

PortfolioLimits supports explicit opt-in limits for maximum position count,
gross exposure, symbol exposure, and sector exposure. An unset policy is None.
No numeric production policy is invented when the current specification has not
frozen one.

Projection creates a new immutable snapshot and supports increasing,
reducing, flattening, and opening signed positions.

PortfolioDecision records the action, reason code, reason, current/projected
gross exposure, projected position count, and a deterministic fingerprint.

## Boundary with Risk

Portfolio approval is not risk authorization.

The intended path is:

    TradeCandidate
       ↓
    Strategy Decision
       ↓
    Portfolio Engine
       ↓
    Risk Engine
       ↓
    ExecutionAuthorization
       ↓
    Independent Safety
       ↓
    Execution Engine

Risk remains authoritative for quantity sizing and frozen risk controls.

## Validation

Dedicated tests cover immutable contract validation, signed long/short
positions, duplicate-symbol rejection, portfolio projection, flattening,
gross exposure, symbol exposure, sector exposure, position count, deterministic
decision fingerprints, and explicit opt-in policy behavior.

## Status

Implemented on branch feat/portfolio-engine.

This module is a portfolio-policy boundary only. It does not establish
profitability, live readiness, or broker readiness.
