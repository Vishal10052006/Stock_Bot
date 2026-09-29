# Evidence Cycle — Post-Phase-12 Integration

This boundary connects the repository's existing research, backtest, OOS, walk-forward, paper-evidence, lineage, and readiness authorities.

## Canonical flow

Trade Outcome -> Experience -> Error Analysis -> Learning Evidence -> Frozen Experiment -> BACKTEST -> LEAKAGE_AUDIT -> OOS -> WALK_FORWARD -> PAPER -> REPRODUCIBILITY -> PROMOTION_REVIEW.

Missing evidence is not converted into a pass. Evidence is bound to immutable artifact identities.

## Authority boundaries

- Backtesting remains the historical replay authority.
- Validation remains the candidate-evidence authority.
- Lineage remains the reproducibility authority.
- Paper evidence remains observation/quality evidence.
- Readiness remains fail-closed and never enables live execution.
- Learning can propose research changes but cannot mutate Strategy/Risk/Safety or broker permissions.
- Promotion remains a separate governance action.

## Operational limitation

The software can validate structure and provenance. It must not manufacture real OOS, walk-forward, paper, latency, calibration, or operational observations.

Live broker execution remains locked.
