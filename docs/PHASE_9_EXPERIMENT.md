# Phase 9 — Experiment Record Contract (P9-17)

Every significant Prediction Bot experiment must record:

- experiment_id
- research_question
- hypothesis
- failure_criterion
- dataset_version
- code_version
- period
- symbols
- observations
- label_distribution
- assumptions
- fixed_parameters
- allowed_change
- method
- baseline_results
- model_results
- stratified_results
- effective_sample_size_notes
- limitations
- interpretation
- decision: KEEP / REJECT / INCONCLUSIVE
- root_cause
- lesson
- next_experiment

The external test partition stays untouched for P9 model selection and calibration.


## S21 reproducibility binding

The experiment-definition layer is now paired with an `ExperimentRecord`.
A completed record stores measured observations, label distribution, baseline/model
results, stratified results, effective-sample notes, limitations, interpretation,
decision, root cause, lesson, and next experiment.

Each record carries the SHA-256 fingerprint of its exact
`ExperimentDefinition`. This binds results to the frozen research specification
without implying that any particular decision is scientifically validated.

The record contract does not itself run a backtest, OOS evaluation, or
walk-forward evaluation. Those execution stages remain separate and must feed
their measured outputs into the record.


## S21 execution boundary

`ExperimentRunner` now provides the explicit execution boundary for one frozen
`ExperimentDefinition`. An executor receives that definition and must return an
`ExperimentRecord` whose fingerprint matches the definition.

The runner intentionally does not invent a dataset, model, backtest, OOS split,
or walk-forward policy. Those components remain explicit inputs to the executor.
This prevents hidden research configuration and keeps experiment policy auditable.

The runner therefore establishes reproducible orchestration, but it is not itself
evidence of model quality, profitability, OOS performance, or walk-forward
performance.


## S21 validation execution adapter

`execute_validation_experiment` connects the experiment boundary to the existing
temporal OOS and walk-forward contracts. The caller must explicitly provide the
dataset, OOS predictor, walk-forward data, evaluator, fold count, and purge
interval.

The adapter records validation structure and deliberately leaves performance
interpretation, model selection, and the final KEEP/REJECT decision outside the
adapter. It therefore cannot manufacture profitability or model-quality claims.

The next integration boundary is an explicit trading/backtest evaluator when a
research experiment defines one.
