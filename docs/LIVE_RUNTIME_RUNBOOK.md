# STOCK_BOT — Runtime Runbook

## Current CLI

The repository exposes real runtime modes through `main.py`.

```text
python main.py --mode ceo-demo
python main.py --mode shadow
python main.py --mode paper
python main.py --mode readiness
python main.py --mode live --confirm-live
```

The default mode remains `ceo-demo` for backward compatibility.

## 1. Synchronize the repository

```bash
cd ~/STOCK_MODEL/Stock_Bot
source .venv/bin/activate

git checkout main
git fetch origin
git reset --hard origin/main
```

## 2. Readiness check

```bash
python main.py --mode readiness
```

This command is deliberately fail-closed. The current repository does not
derive the 17 live-readiness gates automatically from filenames or process
exit codes. A readiness report is only a checklist result; it does not enable
broker connectivity.

## 3. Shadow mode — real market data, no orders

The shadow path uses the existing Upstox Market Data Feed V3 adapter, canonical
market-event validation, and the five-minute NSE candle aggregator.

Required runtime configuration:

```text
UPSTOX_ACCESS_TOKEN
UPSTOX_INSTRUMENT_MAP
```

Example:

```bash
python main.py --mode shadow --symbol RELIANCE --candles 1
```

The process exits after the requested number of completed five-minute candles.
No broker order is created.

For the existing one-event connectivity smoke test:

```bash
python scripts/smoke_test_upstox_feed.py
```

## 4. Paper mode

Paper mode consumes an explicit frozen strategy-ready parquet dataset:

```bash
python main.py \
  --mode paper \
  --input data/paper/frozen_rows.parquet \
  --quantity 1
```

Required decision-time columns:

```text
timestamp
symbol
close
regime
regime_probability
vwap_distance_pct
rvol_20
higher_high
higher_low
lower_low
lower_high
```

Paper mode uses the existing Strategy -> Risk -> ExecutionAuthorization ->
PaperTradingRuntime path and never submits broker orders.

The existing evidence-persistence command remains available:

```bash
python scripts/trading/run_empirical_paper.py \
  --input data/paper/frozen_rows.parquet \
  --dataset-version paper-YYYY-MM-v1 \
  --code-version <git-sha> \
  --evidence-version PAPER-EVIDENCE-v1 \
  --journal data/paper/paper_evidence.jsonl \
  --output data/paper/empirical_paper_report.json
```

## 5. Live mode

Current behavior:

```bash
python main.py --mode live --confirm-live
```

This returns a locked state and does not submit a real-money order.

The repository currently marks live broker execution as locked/disabled and
requires provider-readiness evidence, position reconciliation, operational
controls, and current broker/exchange/compliance verification before activation.
The Upstox execution adapter is also disabled by default.

## 6. Remaining runtime work

The CLI is now mode-aware, but actual end-to-end live execution is not enabled.
The remaining runtime boundary is to connect the existing real market feed and
Phase 21 live-signal path to a verified model artifact, then route approved
signals through Risk -> Independent Safety -> live readiness -> Upstox execution,
with durable reconciliation and operational controls.

The current repository does not contain a safe artifact loader that turns a
registry record into the fitted `LogisticOutcomeModel` and fitted
`FeaturePreprocessor` required by the existing prediction adapter.

The current repository also does not contain `evaluate_live_predictions.py`
on `main`; that earlier validation implementation was on a separate branch.

## 7. Intended future sequence

```text
readiness
   ↓
provider evidence
   ↓
verified model artifact
   ↓
live market data
   ↓
5-min candle
   ↓
Phase 4 indicators
   ↓
Phase 5 features
   ↓
Phase 6 regime
   ↓
Analysis
   ↓
Prediction
   ↓
Strategy
   ↓
Risk
   ↓
Independent Safety
   ↓
Live Readiness
   ↓
Upstox execution
   ↓
Broker reconciliation
   ↓
Monitoring / audit journal
```

Only after each boundary has a current implementation and explicit evidence
should the live command be changed from `LOCKED` to executable behavior.
