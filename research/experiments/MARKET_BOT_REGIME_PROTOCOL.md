# Market Bot Regime Research Protocol

Production V1 remains the deterministic Phase 6 regime detector.

Any K-Means, GMM, HMM or other statistical regime model must be evaluated as
a separate experiment.

Required sequence:

1. Freeze the deterministic baseline.
2. Freeze the feature set and data availability rules.
3. Build chronological walk-forward folds.
4. Fit only on the training interval of each fold.
5. Evaluate only on the subsequent test interval.
6. Compare robustness, stability, persistence and transition behavior.
7. Do not promote automatically.
8. Record model, data, feature and experiment versions.

The Market Bot research harness returns metrics and explicitly sets
promotion to false. Promotion requires a separately reviewed decision.
