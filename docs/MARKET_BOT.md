# Market Bot

Market Bot is a descriptive market-context layer. It does not make trading
decisions, size positions, approve risk, or execute orders.

## Roadmap status

- MB-00 Architecture Audit & Boundary Freeze: implemented
- MB-01 Market Universe & Benchmark: implemented
- MB-02 Market Trend Engine: implemented
- MB-03 Range / Trend Structure: next

## MB-01

Historical universe selection is delegated to the existing
point-in-time universe infrastructure.

The Market Bot adapter preserves policy version, source, and point-in-time
date. Current Upstox identity mapping is not used to infer historical
membership.

## MB-02

The deterministic trend engine consumes timestamped benchmark OHLC data and
produces descriptive trend context:

- fast moving average
- slow moving average
- price relative to moving averages
- fast/slow MA relationship
- fast and slow returns
- normalized slow-MA slope
- bounded descriptive trend strength
- UP / DOWN / MIXED / UNAVAILABLE state

All rolling calculations are causal: the value at timestamp t depends only
on observations at or before t.

The engine is intentionally not a signal generator.
