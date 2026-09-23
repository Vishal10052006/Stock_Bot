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
