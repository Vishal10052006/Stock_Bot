# STOCK_BOT - Risk Engine

The Risk Engine is the deterministic control layer between Strategy and
Execution. It consumes a causal TradeCandidate plus point-in-time portfolio
and market context. It never predicts, generates signals, calls a broker, or
decides market direction.

## R0-R20 status
The risk branch contains the R0-R20 implementation set.

## Boundary
StrategyDecision -> TradeCandidate -> RiskEngine -> RiskDecision -> ExecutionAuthorization

## Frozen paper policy
- Risk per trade: 0.5% of current equity.
- Daily loss limit: 1.5% of starting equity.
- Maximum entries/day: 5.
- Maximum open positions: 3.
- Maximum gross exposure: 75% of equity.
- Minimum target: 1.5R.
- Initial paper capital: Rs 100,000.
- Live execution remains locked.

## Safety and causality
The engine fails closed on invalid candidate/context, stale context,
daily-loss breach, drawdown breach, closed session, missing required liquidity,
market stress, or an active kill switch.

Historical risk decisions may use only information available at the decision
timestamp. Future price, volatility, liquidity, portfolio state, sector
membership and transaction costs are forbidden historical inputs.

## Existing infrastructure reused
TradeCandidate, StrategyDecision, execution authorization, backtest cost/fill
models, historical backtest engine, and existing test/logging infrastructure.

## Known limitations
v1.0 controls for sector/correlation, market impact, spread and regime-aware
risk are explicit contracts; they are not claimed to improve performance until
validated through backtest, OOS, walk-forward and paper evidence.
