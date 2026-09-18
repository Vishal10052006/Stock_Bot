# STOCK BOT — Trading Specification

**Specification version:** 1.0
**Status:** FROZEN FOR RESEARCH AND PAPER TRADING
**Market:** NSE
**Segment:** Equity Cash
**Timezone:** Asia/Kolkata (IST)

---

## 1. Purpose

This document defines the trading contract for STOCK BOT.

The strategy, machine-learning models, feature engineering pipeline,
backtester, paper-trading engine and future execution infrastructure
must operate within these constraints.

No downstream component may silently change these assumptions.

Any change requires a controlled specification revision followed by
appropriate revalidation.

---

## 2. Market

### Exchange

NSE — National Stock Exchange of India.

### Segment

Equity cash segment.

### Trading style

Intraday only.

STOCK BOT must not carry an intraday research/paper position overnight.

---

## 3. Instrument Universe

The initial research universe consists of liquid NSE-listed equities.

Universe selection must be deterministic and versioned.

The system must not select instruments retrospectively because they
performed well during the test period.

Liquidity and eligibility rules belong to the market-data/universe
pipeline and must be available without future information.

NIFTY and sector/index context may be used as contextual market data,
but must be timestamp-aligned and independently validated.

---

## 4. Timeframe

### Primary timeframe

5-minute candles.

All initial indicator, feature, strategy and backtesting development
must use the 5-minute decision timeframe unless a research experiment
explicitly defines another timeframe.

The first 5-minute candle begins at:

09:15 IST

---

## 5. Trading Session

### Allowed strategy session

09:15–15:30 IST.

Special/pre-open/closing-session behavior is excluded from the initial
strategy unless deliberately modeled and separately validated.

### End-of-day rule

All intraday positions must be closed before the normal equity market
close.

The system must not intentionally carry an intraday position overnight.

---

## 6. Direction

### Research and paper trading

Both directions are supported:

- LONG
- SHORT

### Live trading

Short-selling mechanics are not assumed to be automatically valid for
live deployment.

They require separate broker, exchange and regulatory validation before
live activation.

---

## 7. Initial Paper Capital

Initial paper account:

₹100,000

This is the starting capital for the initial paper-trading configuration.

Performance must be measured as both:

- absolute P&L
- percentage return/equity change

Capital is not a guarantee of profitability.

---

## 8. Risk Per Trade

Maximum planned loss per new trade:

0.5% of current available equity.

For an initial ₹100,000 account:

0.5% = ₹500 maximum planned risk.

Position size must be derived from:

position_size =
risk_budget / stop_distance

with appropriate price/quantity rounding and broker/instrument
constraints.

A position must never be sized first and have risk calculated
afterward.

---

## 9. Maximum Daily Loss

Hard daily loss limit:

1.5% of the day's starting equity.

For a ₹100,000 starting day:

1.5% = ₹1,500.

Daily loss accounting must include realized and unrealized trading P&L
and applicable execution costs.

When the limit is reached:

- no new trades may be opened;
- the trading system enters a risk-blocked state;
- the AI/model cannot override the block;
- any required position handling must follow the independent risk and
  safety policy.

The daily limit resets only at the beginning of a new eligible trading
session.

---

## 10. Maximum Trades Per Day

Hard maximum:

5 trade entries per trading day.

Normal research target:

approximately 2–3 trades/day.

The 2–3 figure is a target observation, not a requirement to manufacture
trades.

The system must prefer:

NO TRADE

over forcing additional trades.

---

## 11. Maximum Open Positions

Maximum simultaneous open positions:

3.

The risk engine must reject a new position when the limit would be
exceeded.

---

## 12. Maximum Gross Exposure

Maximum aggregate gross market exposure:

75% of available trading equity.

Long and short exposure must both be included in gross exposure
calculation.

The exposure calculation must use current position quantities and
current validated prices.

---

## 13. Entry

A trade may be considered only after a complete validated decision
pipeline produces an actionable signal.

Required conceptual pipeline:

Market Data
→ Validation
→ Candle
→ Indicators
→ Features
→ Regime
→ Strategy/Model
→ Trading Decision
→ Risk Validation
→ Paper/Execution Layer

The signal model does not have financial execution authority.

Entry price must be based on the price information actually available
at the decision/arrival time.

The system must never assume a fill at a price that was not available
at that time.

---

## 14. No-Trade Conditions

NO TRADE is a first-class outcome.

Examples of mandatory no-trade conditions include:

- stale market data;
- invalid candle;
- missing required features;
- unresolved timestamp/data-quality problem;
- risk limit reached;
- daily loss limit reached;
- maximum open positions reached;
- maximum exposure reached;
- maximum trades reached;
- invalid stop distance;
- invalid price;
- insufficient liquidity;
- market/symbol eligibility failure;
- safety/kill-switch block;
- incomplete strategy/model context.

A model's desire to trade cannot override any hard no-trade condition.

---

## 15. Stop-Loss

The initial research stop methodology is:

STRUCTURE + ATR constrained stop.

The stop must be based only on information available at decision time.

For LONG:

- primary structural reference is the relevant validated swing/support
  level;
- ATR provides a volatility constraint.

For SHORT:

- primary structural reference is the relevant swing/resistance level;
- ATR provides a volatility constraint.

The exact ATR multiplier and structural lookback are strategy parameters
and must be versioned and evaluated through backtesting.

They must not be changed during an evaluation run.

---

## 16. Target

Initial research target:

minimum 1.5R.

Where:

R = initial planned monetary risk of the trade.

Example:

Risk = ₹500

Minimum target profit before costs = ₹750.

The target must be evaluated after realistic transaction costs and
slippage.

A strategy is not considered successful merely because gross target
logic is profitable before costs.

---

## 17. Maximum Holding Time

Initial maximum holding time:

60 minutes.

A position reaching the maximum holding duration must be exited
according to the execution/fill model.

The time-exit decision must use the system's authoritative timestamps.

---

## 18. Position Sizing

Position sizing must be risk-first.

Required conceptual calculation:

risk_budget = equity × risk_per_trade

stop_distance = abs(entry_price - stop_price)

raw_quantity = risk_budget / stop_distance

Final quantity must then respect:

- exchange/broker quantity rules;
- instrument constraints;
- exposure limits;
- available capital;
- maximum position limits;
- liquidity constraints.

If a valid quantity cannot be produced within all constraints:

NO TRADE.

---

## 19. Transaction Costs

Backtesting and paper-trading evaluation must not assume zero costs.

The cost model must be configurable and versioned.

It must account for applicable components such as:

- brokerage;
- STT;
- exchange transaction charges;
- GST;
- SEBI-related charges;
- stamp duty;
- applicable statutory charges;
- slippage.

Exact broker/exchange charge schedules must be verified when the
broker-specific execution layer is implemented.

The strategy must be evaluated using net P&L after costs.

---

## 20. Slippage

Slippage must be explicitly modeled.

The backtester must not assume every entry and exit receives the
observed candle price.

The slippage model must eventually support sensitivity analysis.

At minimum, research must evaluate whether strategy conclusions remain
valid under reasonable increases in assumed slippage.

---

## 21. Data Integrity Requirements

Trading decisions require validated market data.

The system must detect and appropriately handle:

- missing candles;
- duplicate candles;
- invalid OHLC relationships;
- invalid timestamps;
- timezone errors;
- stale data;
- disconnected feeds;
- symbol eligibility problems;
- illiquidity;
- corporate-action/data-adjustment issues.

No downstream model may silently repair bad market data in a way that
creates artificial trading information.

---

## 22. Causality / Look-Ahead Rule

Every trading feature and decision input must use only information that
would have been available at the decision timestamp.

Future prices may be used to generate research labels/outcomes only after
the feature/decision dataset has been constructed.

Future information must never enter:

- indicators used for the decision;
- features;
- regime state;
- strategy conditions;
- model inputs;
- position sizing;
- entry decisions.

---

## 23. Market and Sector Context

Where market/index/sector context is used, it must be independently
sourced and timestamp-aligned.

Examples include:

- NIFTY return;
- NIFTY trend;
- NIFTY volatility;
- sector return;
- sector trend;
- market breadth where available.

STOCK BOT must never fabricate market or sector values from the
individual stock's own candles.

If required contextual data is unavailable or invalid:

NO TRADE,

unless the strategy explicitly defines that context as optional.

---

## 24. Paper Trading

Paper trading must use simulated capital while consuming the same
validated live-data pathway intended for later deployment.

Paper trading must measure:

- signal frequency;
- fills;
- slippage;
- latency;
- false signals;
- drawdown;
- regime behavior;
- model calibration;
- operational stability.

Paper trading is evidence collection, not permission for live capital.

---

## 25. Live Trading Lock

Live trading is LOCKED.

No code path may enable live financial execution merely because:

- a model is profitable;
- paper trading produced profits;
- confidence is high;
- a user command asks for immediate execution.

Live activation requires all required validation and safety gates.

The roadmap defines live readiness only after paper evidence, broker
integration, safety controls and current compliance checks.

---

## 26. Required Validation Gates

Before live trading, STOCK BOT must pass the applicable research and
operational gates, including:

1. validated historical data;
2. validated indicators;
3. leakage-safe features;
4. target/label validation;
5. deterministic baseline strategy;
6. model validation;
7. realistic backtesting;
8. bias/leakage audit;
9. out-of-sample validation;
10. walk-forward validation;
11. paper trading evidence;
12. risk controls;
13. monitoring;
14. independent kill switch;
15. broker integration and reconciliation;
16. current broker/exchange/regulatory verification.

The final test period must remain genuinely unseen until the research
process is frozen.

---

## 27. Risk Authority

The risk engine has veto authority over the strategy/model.

Authority hierarchy:

Data/Safety
→ Risk
→ Trading Decision
→ Strategy/Model

A strategy/model cannot override:

- daily loss;
- position limits;
- exposure limits;
- invalid prices;
- stale data;
- kill switch;
- safety blocks.

---

## 28. Change Control

This specification is frozen for a research/evaluation run.

Any change to:

- market;
- universe;
- timeframe;
- session;
- risk;
- daily loss;
- position limits;
- exposure;
- stop;
- target;
- holding period;
- costs;
- slippage;
- execution assumptions

requires:

1. specification revision;
2. version increment;
3. affected dataset/backtest identification;
4. backtest;
5. appropriate validation;
6. documentation of the reason for change.

A profitable result must never be obtained by silently changing the
specification after seeing the result.

---

## 29. Performance Objective

The historical project objective of approximately ₹500–₹1,000/day is
a research target to evaluate, not a guaranteed income target.

The primary success criterion is:

POSITIVE EXPECTANCY AFTER REALISTIC COSTS
+
ROBUST UNSEEN PERFORMANCE
+
STABLE PAPER-TRADING BEHAVIOR

Return alone is insufficient.

---

## 30. Status

Phase 1 specification status:

FROZEN FOR INITIAL RESEARCH/PAPER CONFIGURATION

Live execution status:

LOCKED

Next dependent phase:

Phase 2 — Historical Market Data Pipeline
