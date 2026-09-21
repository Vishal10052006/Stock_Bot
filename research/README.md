# Research Bot — Production Layer

## Real source adapters

- NSE corporate-filings CSV: announcements, actions and financial-result exports.
- RBI public RSS.
- PIB public RSS.
- Generic RSS/Atom feeds for additional news providers.

NSE corporate-filings pages expose CSV download controls and exchange
broadcast/dissemination timestamps. The pipeline uses dissemination time as
the point-in-time boundary when supplied.

## Historical corpus

Archive normalized documents in append-only JSONL. Historical experiments
must preserve the original available_at timestamp. Live fetch time must never
replace historical availability.

## Research features

The causal feature builder produces transparent aggregates: document count,
source count, mean sentiment, positive/negative fractions and event counts.

## Leakage audit

ResearchLeakageAuditor checks future features, forbidden target fields, label
timing and duplicate decision rows.

## Experiment protocol

The experiment harness computes the required multiclass metrics and a
majority/class-prior baseline. It deliberately returns UNDECIDED; the
researcher must apply the frozen failure criterion and compare against the
frozen BaselineStrategy. It does not generate P&L claims.

## Production boundary

External LLM/vector services remain explicit adapters. No credentials,
synthetic evidence or hidden provider is embedded in the repository.


## Completion workflow

1. Download real NSE announcement CSV snapshots for the market periods being
   evaluated. NSE exposes 1D/1W/1M/3M/6M/1Y and Custom ranges with CSV download
   on its Corporate Filings Announcement page.
2. Materialize overlapping CSV files with
   scripts/research/materialize_nse_corpus.py. The resulting manifest records
   every raw-file SHA-256 and a deterministic corpus fingerprint.
3. Pair the corpus with raw completed OHLCV candles. Do not use a filtered
   training dataset as a substitute when exact future target candles are
   required.
4. Build point-in-time ResearchMarketObservation records. A research document
   is eligible only when its available_at is no later than the decision candle
   close, and a target candle must exist at the exact requested future horizon.
5. Run research/evaluation/oos.py on the frozen observations. No threshold or
   model parameter is learned from the test folds.
6. Export the ResearchAnalysisContext for the downstream Analysis Bot.
7. Run the structural production audit and record the corpus fingerprint, OOS
   fold count, rejection counts and source coverage.

The final audit may pass structural readiness while the research usefulness
decision remains UNDECIDED. Those are deliberately separate claims.
