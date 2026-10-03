# Personal V1 Live-Review Preflight

This preflight is for the personal STOCK_BOT real-market workflow.

## What it does

`python -m scripts.validate_live_review_env` validates the local configuration shape required by the V1 live-review runtime:

- Upstox market-feed credential and instrument mapping are present;
- live Risk observation settings are present;
- the Risk account token environment variable is present;
- the persistent day-state parent directory exists;
- JSON and numeric settings have valid types.

## What it does not do

A successful preflight is **not** a trading-readiness approval.

It does **not**:

- contact Upstox;
- fetch live account state;
- validate market conditions;
- validate the model artifact;
- produce a BUY/SELL decision;
- submit, modify, cancel, or exit broker orders.

The V1 authority remains:

**Real Market → Research → Analysis → Prediction → Strategy → Risk → Human Review → Manual BUY/SELL**

## Usage

Run on the trading machine before starting the live-review runtime:

    python -m scripts.validate_live_review_env

The command intentionally reports only configuration status and never prints credential values.

A passing preflight must still be followed by the runtime's live account freshness/risk gates and the human review step.
