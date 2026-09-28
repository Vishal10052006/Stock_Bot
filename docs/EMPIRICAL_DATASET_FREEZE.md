# EMP-02 — Freeze the Empirical Paper Dataset

EMP-02 establishes the immutable dataset identity boundary before an empirical paper run.

The repository does not currently contain a committed real paper dataset. Therefore this step provides the validator and manifest generator; it does not fabricate market observations.

## Command

```bash
python scripts/trading/freeze_paper_dataset.py \
  --input <frozen-strategy-ready.parquet> \
  --dataset-version paper-YYYY-MM-v1 \
  --output data/paper/paper_dataset_manifest.json
```

## Manifest

The manifest records:

- dataset version;
- source path;
- SHA-256 of the exact Parquet bytes;
- row count;
- symbol universe;
- chronological period;
- complete column list;
- required strategy columns.

The source Parquet is never rewritten by the freeze command.

## Validation rules

The freeze fails closed when:

- required strategy columns are missing;
- the dataset is empty;
- timestamps are invalid;
- rows are not already chronological;
- duplicate timestamp/symbol observations exist;
- symbols are empty;
- close prices are non-positive.

The SHA-256 fingerprint identifies the exact artifact used for the empirical run. A later change to the Parquet bytes produces a different fingerprint.

## Evidence boundary

A valid manifest proves **dataset identity and structural validity only**. It does not prove predictive performance, profitability, OOS validity, or live readiness.
