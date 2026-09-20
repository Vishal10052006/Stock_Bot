# STOCK_BOT ↔ Research Bot Alignment

This document follows the supplied alignment diagram and preserves one system rather than creating a competing trading stack.

| STOCK_BOT phase | Research Bot dependency | Rule |
|---|---|---|
| 0 Architecture | RB-0 | Contracts align with existing system boundaries. |
| 1 Trading Spec | RB-0 | Research obeys frozen market/session/causality rules. |
| 2 Data Infrastructure | RB-1/RB-2 | Research sources and raw documents use provider/storage boundaries. |
| 3 Live Data Pipeline | RB-1/RB-4 | Live research must obey observation/availability time. |
| 4 Indicator Engine | — | Existing indicator engine remains authoritative for technical indicators. |
| 5 Feature Engine | RB-13 | Research features are validated before ML consumption. |
| 6 Market Regime | RB-8/RB-13 | Impact/context can be consumed alongside existing regime features. |
| 7 Target Labeling | — | Research must never access future labels while constructing features. |
| 8 Baseline Strategy | — | Research does not replace the deterministic baseline. |
| 9 ML Model | Research features tested | Only validated research features may enter ML experiments. |
| 10 Decision Engine | RB-12 | Decision engine may consume ResearchContext; research has no authority. |
| 11 Risk Engine | — | Risk veto remains independent and above strategy/research. |
| 12 Backtesting | Research features backtested | Research-derived features must pass causal and OOS testing. |
| 13 Leakage Audit | RB-4 + RB-13 | `available_at` and future-field rejection are mandatory. |
| 14 OOS Validation | RB-13 | Research feature usefulness must be tested on unseen periods. |
| 15 Walk Forward | RB-13 | Point-in-time research is required during historical replay. |
| 18 Learning Engine | Research improvement loop | Learning may improve research components without changing frozen specs silently. |
| 21 Live Signal Engine | Live Research Context | Live research is context only; strategy/risk retain authority. |
| 23 Monitoring | RB-14 | Research freshness, failures and PIT rejections are observable. |
| 27 Advanced AI | Advanced Research Intelligence | Advanced models remain replaceable adapters with evidence requirements. |
