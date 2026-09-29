# Evidence Cycle — Post-Phase-12 Integration

The evidence cycle connects existing research, backtest, OOS, walk-forward, paper evidence, lineage and readiness boundaries without creating a second validation or trading engine.

## Flow

BACKTEST -> LEAKAGE_AUDIT -> OOS -> WALK_FORWARD -> PAPER -> REPRODUCIBILITY

The cycle may produce eligibility evidence. It never authorizes live execution.

## Required rules

- Evidence stages must be supplied from actual artifacts.
- Missing stages remain missing; they are not synthesized as passes.
- Stage artifact fingerprints must be preserved.
- Candidate/model identity must match validation artifacts.
- Learning remains research-side.
- Promotion requires explicit governance approval.
- Live broker execution remains independently locked.

## Current repository authorities

- backtesting/engine.py — historical replay.
- self_learning/validation.py — structural validation policy.
- self_learning/validation_orchestrator.py — candidate-bound validation run.
- experiments/lineage.py — reproducibility lineage.
- execution/readiness.py — fail-closed readiness gate.
- experiments/paper_quality.py — structural paper-evidence quality.

This document is an integration contract, not a profitability claim.
