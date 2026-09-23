# STOCK_BOT — Phase 11 Direct Build

Risk Engine build is anchored to the existing Strategy -> Risk -> Execution architecture.

Current repository Risk Engine already provides risk-first sizing, target construction, daily-loss, entries/day, open-position, gross-exposure, liquidity, duplicate-symbol and kill-switch checks.

The repository already has causal Structure + ATR stop construction in `trading/signals/candidate.py`. Do not duplicate this logic inside Risk; Risk validates and sizes the candidate.

Next implementation sequence:
11.2 Stop validation/hardening
11.3 Target engine
11.4 Position-sizing constraints
11.5 Exposure controls
11.6 Concentration/correlation
11.7 Daily limits/drawdown
11.8 Volatility adjustment
11.9 Kill switch
11.10 Unified Risk Decision Engine
11.11 Integration
11.12 Full validation
