# STOCK_BOT — Phase 21 Live Signal Engine

**Implementation status:** Engineering boundary implemented on the shadow runtime.

## Boundary

`LiveSignalEngine` consumes a causal `StrategyInput` and invokes the authoritative `StrategyEngine`. It emits an immutable `LiveSignal` observation containing timestamp, symbol, direction, strategy version, rationale, prediction metadata, regime metadata, feature version, and provenance.

## Controls

- Decision timestamps must be timezone-aware.
- Future-dated inputs are rejected.
- Stale inputs are rejected using a configurable freshness window.
- Per-symbol signal timestamps must be strictly increasing.
- Signal IDs are deterministic from timestamp, symbol, strategy version, and direction.
- The engine has no Risk sizing authority.
- The engine has no Safety override.
- The engine has no Paper/Broker submission authority.
- Every signal evidence record carries `live_broker_order_submission=false`.

## Runtime integration

The M20 shadow runtime exposes `evaluate_live_signal(...)` and journals each observed signal as `LIVE_SIGNAL_OBSERVED`. The signal is therefore observable and replayable without becoming an order.

## Next boundary

The next downstream step is Risk evaluation of a signal. A signal alone must never create an execution authorization or broker order.
