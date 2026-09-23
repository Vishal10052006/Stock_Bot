# STOCK BOT — S21-S28 Research Validation Roadmap

| Stage | Status | Repository boundary |
|---|---|---|
| S21 Experiments | COMPLETE | experiments/definition.py, record.py, runner.py, executor.py |
| S22 Evaluation | COMPLETE | experiments/evaluation.py |
| S23 OOS | COMPLETE | backtesting/oos.py |
| S24 Walk-forward | COMPLETE | backtesting/walk_forward.py |
| S25 Failure analysis | COMPLETE | experiments/failure_analysis.py |
| S26 Monitoring | COMPLETE | experiments/monitoring.py |
| S27 Lineage | COMPLETE | experiments/lineage.py |
| S28 Controlled self-learning | COMPLETE | experiments/self_learning.py |

## Control boundaries

- **S21:** experiment specifications are immutable and fingerprinted.
- **S22:** recorded measurements are checked for structural and numerical integrity.
- **S23:** final test data is kept outside predictor training context and protected against mutation.
- **S24:** chronological expanding folds use explicit purge intervals and test isolation.
- **S25:** failure analysis reports evidence gaps and process findings without inventing market causes.
- **S26:** monitoring reports operational error, staleness, and optional prediction-distribution drift.
- **S27:** lineage binds experiment definition, measured record, dataset/code versions, and artifacts.
- **S28:** learning produces proposals only; allowed changes must be explicitly declared and validated again.

## Important evidence boundary

Completion of these repository controls does **not** mean that the stock strategy has
demonstrated profitability, predictive superiority, or live-trading readiness.

Those claims require actual frozen datasets, realistic costs/slippage, OOS and walk-forward
measurements, paper-trading evidence, and the remaining production controls defined by the
trading specification.

## Research-readiness integration status

The research validation chain is now connected to the readiness provenance boundary through
`execution.research_readiness.build_research_readiness_evidence(...)`.

For one `ExperimentLineageExecution`, the adapter verifies lineage identity and binds:

- baseline/model readiness to the experiment lineage ID;
- OOS readiness to the exact OOS artifact fingerprint;
- walk-forward readiness to the exact walk-forward artifact fingerprint;
- historical-backtest readiness to the exact backtest artifact fingerprint when a backtest
  was explicitly supplied.

Dataset and code versions are derived from the same lineage. Artifact substitution and
missing required backtest evidence fail closed. The resulting evidence can be supplied to
`LiveReadinessGate(..., require_provenance=True)`, but it does not set readiness gates to
true or enable live execution.
