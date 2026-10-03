# V1 Manual Decision Authority

## Boundary

V1 real-market decision support is owned by `trading.live.manual_decision`.
The module consumes the existing Prediction, Strategy, and Risk authorities and
returns an auditable manual-review decision.

```text
Real Market
   -> Research
   -> Analysis
   -> Prediction
   -> Strategy
   -> Risk
   -> V1 Signal
   -> Human Review
   -> MANUAL BUY / SELL
```

## Execution rule

- No broker client is accepted by the manual decision function.
- No order submission, modification, cancellation, or fill state is produced.
- `manual_execution_status="MANUAL_BUY_SELL_REQUIRED"` means the signal passed
  the existing Strategy/Risk boundary and requires the human operator to act.
- `trade_id` remains `None` until a separate, explicitly approved execution
  workflow exists.
- The legacy `trading.paper.canonical_paper_callback` module is now only a
  compatibility import shim.

## Migration

The paper runtime may continue to exist for historical validation and testing.
It is not the authority for the V1 manual real-money decision contract.

## Verification

`tests/trading/test_manual_decision_authority.py` verifies that the V1 decision
implementation is importable from `trading.live` and does not expose a broker
order surface.
