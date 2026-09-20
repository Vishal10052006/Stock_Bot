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
