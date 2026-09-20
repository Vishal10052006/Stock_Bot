# STOCK_BOT Research Bot — Step 2 Implementation

## Scope

This package implements the deterministic Research Bot foundation for RB-0 through RB-14 without changing the existing market/trading stack and without modifying `memory/long_term_memory.json`.

## Phase mapping

| Phase | Implementation |
|---|---|
| RB-0 Contract | `research/contracts/` |
| RB-1 Source Layer | `research/providers/`, `ingestion/` |
| RB-2 Raw Storage | `research/storage/` |
| RB-3 Entity Resolution | `research/entities/` |
| RB-4 Causal Time | `research/causal/` |
| RB-5 Normalization | `research/normalization/` |
| RB-6 Event Detection | `research/events/` |
| RB-7 Sentiment | `research/sentiment/` |
| RB-8 Impact Analysis | `research/impact/` |
| RB-9 Historical Memory | `research/memory/` |
| RB-10 RAG/Research Memory | `research/retrieval/` |
| RB-11 Report Generator | `research/reports/` |
| RB-12 Analysis Integration | `research/integration/` |
| RB-13 Feature Validation | `research/features/` |
| RB-14 Monitoring | `research/monitoring/` |
| RB-17.2.1 Historical Archive Contract | `research/corpus/archive.py` |
| RB-17.2.4 Historical Archive JSONL Ingestion | `research/corpus/archive_jsonl.py` |

## Important research safeguards

1. `available_at` is the point-in-time gate.
2. ResearchContext filters documents before event/sentiment processing.
3. Target/future fields are rejected from research features.
4. Every event retains `document_id` and evidence.
5. Sentiment and impact are evidence/context, not trading decisions.
6. The deterministic lexical components are replaceable baselines, not claims of predictive edge.
7. Raw research storage is separate from the existing long-term memory system.

## Not implemented as hidden assumptions

External news/filing APIs, paid feeds, vector databases, LLM APIs, and production database credentials are provider/deployment choices and therefore remain explicit adapters. No fake provider or synthetic market evidence is introduced.
