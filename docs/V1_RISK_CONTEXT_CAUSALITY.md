# V1 Risk Context Causality Hardening

## Purpose

The V1 manual-review Risk boundary must never evaluate a decision whose timestamp is later than the account/portfolio observation used to authorize that decision.

## Invariant

For a verified live Risk context:

- as_of is the timestamp represented by the observed account state.
- observed_at is when the runtime validates that state.
- decision_timestamp is the timestamp of the market decision/candle.
- The decision timestamp must not be in the future relative to observed_at.
- The account observation may occur after the market candle because the runtime obtains broker account state after the market observation.

A future-dated decision is therefore rejected fail-closed with:

`decision timestamp is in the future relative to risk observation`

## Safety boundary

This change does not add broker execution authority. V1 remains:

Real Market → Research → Analysis → Prediction → Strategy → Risk → Human Review → manual BUY/SELL

Broker order submission remains disabled.

## Verification

Regression coverage includes:

- accepted fresh causal context;
- stale-context rejection;
- future decision timestamp rejection;
- invalid live-account state rejection.
