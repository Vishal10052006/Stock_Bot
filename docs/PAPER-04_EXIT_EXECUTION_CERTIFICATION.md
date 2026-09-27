# PAPER-04 — Approved Exit Execution Certification

## Objective

Certify the execution boundary for stop, target and maximum-holding-time exits.

The historical/backtest layer owns detection of exit conditions. Execution consumes the resulting Risk-approved exit authorization and applies the exact approved quantity to the observed position.

## Certified cases

- Full long-position stop exit.
- Full short-position target exit.
- Partial long-position maximum-holding-time exit.
- Partial short-position exit.
- Exit quantity cannot exceed current position.
- Exit direction must oppose the signed position.
- Duplicate exit submission is idempotent.
- Flat-position exit is rejected.

## Boundary

Exit condition -> Risk authorization -> Safety -> Execution -> Paper broker -> confirmed fill -> position update

Execution does not independently decide when a stop, target or time condition has occurred.

## Safety guarantees

- Execution cannot enlarge Risk-approved exit quantity.
- Execution cannot reverse a position through an oversized exit.
- Same client-order identity cannot create a second broker order.
- Long and short signed positions are both supported.
- Live Upstox execution remains locked.

## Definition of Done

- [x] Stop-exit execution path exercised.
- [x] Target-exit execution path exercised.
- [x] Time-exit execution path exercised.
- [x] Partial exits exercised.
- [x] Long and short exits exercised.
- [x] Oversized exits rejected.
- [x] Direction mismatch rejected.
- [x] Duplicate exits idempotent.
- [x] Flat-position exits rejected.
- [ ] Live broker certification - separate future gate.
