"""Tests for the explicit evidence-cycle dataset entrypoint."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.run_evidence_cycle import main


def _write_dataset(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "timestamp": "2026-09-01T09:15:00Z",
                "symbol": "ITC",
                "label": "NO_EDGE",
                "as_of_date": "2026-09-01",
                "feature_a": 1.0,
            },
            {
                "timestamp": "2026-09-01T09:20:00Z",
                "symbol": "ITC",
                "label": "LONG_SUCCESS",
                "as_of_date": "2026-09-01",
                "feature_a": 2.0,
            },
        ]
    ).to_parquet(path, index=False)


def test_cli_verifies_explicit_snapshot_and_marks_other_stages_missing(
    tmp_path,
    monkeypatch,
):
    dataset = tmp_path / "phase9_dataset_test.parquet"
    output = tmp_path / "manifest.json"
    _write_dataset(dataset)

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_evidence_cycle.py",
            "--dataset",
            str(dataset),
            "--dataset-version",
            "phase9-test-v1",
            "--source",
            "pytest",
            "--created-at",
            "2026-09-30T00:00:00Z",
            "--feature-schema-version",
            "v1.0",
            "--label-definition-version",
            "v1.0",
            "--out",
            str(output),
        ],
    )

    assert main() == 0
    manifest = __import__("json").loads(output.read_text(encoding="utf-8"))

    assert manifest["status"] == "DATASET_VERIFIED"
    assert manifest["dataset"]["rows"] == 2
    assert manifest["promotion_status"] == "NOT_REVIEWED"
    assert manifest["live_execution"] == "LOCKED"
    assert all(
        status == "REQUIRED_ARTIFACT_NOT_SUPPLIED"
        for status in manifest["evidence_status"].values()
    )


def test_cli_fails_for_missing_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_evidence_cycle.py",
            "--dataset",
            str(tmp_path / "missing.parquet"),
            "--dataset-version",
            "v1",
            "--source",
            "pytest",
            "--created-at",
            "2026-09-30T00:00:00Z",
            "--feature-schema-version",
            "v1",
            "--label-definition-version",
            "v1",
        ],
    )

    with pytest.raises(ValueError, match="dataset file does not exist"):
        main()
