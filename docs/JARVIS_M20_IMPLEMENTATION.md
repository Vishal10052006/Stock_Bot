# STOCK_BOT — JARVIS M20 Implementation

This document records the implementation boundaries for the roadmap's M20.1–M20.7 control plane.

## Implemented

- M20.1 Runtime Orchestrator — fail-closed SHADOW runtime, environment validation, health/evidence, controlled startup.
- M20.2 Live Market Feed — existing Upstox V3 feed → validation → candle aggregation → bounded causal shadow buffer.
- M20.3 Live Decision Loop — live-ready causal rows can be routed through the existing PaperDecisionLoop; every strategy/risk/authorization/paper result is traceable through ShadowDecisionRecorder.
- M20.4 Internet Research Engine — ApprovedResearchRuntime composes approved RBI/PIB providers with the existing point-in-time ResearchContextBuilder.
- M20.5 Learning Engine — ControlledLearningRuntime consumes Phase-17/18 evidence through the existing LearningEngine and creates bounded Phase-19 candidate proposals only when an explicit frozen experiment definition and parameter-change mapping are supplied.
- M20.6 JARVIS Scheduler — lifecycle phases, timezone-aware phase resolution, once-per-phase deduplication, and fail-closed error handling.
- M20.7 Dashboard — one JSON/HTML operator view composed from lifecycle and shadow evidence.

## Safety invariant

Every M20 component explicitly reports live_broker_order_submission=false. The JARVIS lifecycle is a control plane; Monitoring is observational; Learning creates research candidates only; and the shadow decision boundary terminates at paper execution.

No M20 implementation unlocks broker order submission.