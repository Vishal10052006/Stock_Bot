from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from scripts.trading.analyze_risk_capacity import (
    Scenario,
    _load_input,
    _manifest_provenance,
    _verify_manifest,
    run_scenario,
)


def _rows() -> pd.DataFrame:
    # Causal strategy-ready fixture with a LONG signal whose risk-first
    # quantity intentionally exceeds the frozen 75% gross-exposure ceiling.
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-09-21T10:00:00+05:30",
                "symbol": "TEST",
                "close": 100.0,
                "regime": "TREND_UP",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 2.0,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
                "atr_14": 0.01,
                "support_20": 99.99,
            },
            {
                "timestamp": "2026-09-21T10:05:00+05:30",
                "symbol": "TEST",
                "close": 101.0,
                "regime": "TREND_UP",
                "regime_probability": 0.9,
                "vwap_distance_pct": 0.02,
                "rvol_20": 2.0,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
                "atr_14": 0.01,
                "support_20": 100.99,
            },
        ]
    )


def test_counterfactual_scenario_is_explicit_and_tracks_gross_rejection():
    result = run_scenario(
        _rows(),
        Scenario("frozen_75_hard_reject", 0.75, False),
    )

    assert result["scenario"]["max_gross_exposure"] == 0.75
    assert result["scenario"]["allow_resize"] is False
    assert result["strategy_signals"] >= 1
    assert result["gross_exposure_rejections"] >= 1
    assert result["risk_rejection_reasons"]["MAX_GROSS_EXPOSURE"] >= 1
    assert "claim_boundary" not in result


def test_resize_counterfactual_can_convert_capacity_rejection_to_fill():
    result = run_scenario(
        _rows(),
        Scenario("frozen_75_resize_enabled", 0.75, True),
    )

    assert result["strategy_signals"] >= 1
    assert result["paper_fills"] >= 1
    assert result["risk_rejection_reasons"].get("MAX_GROSS_EXPOSURE", 0) == 0


def test_load_input_preserves_candidate_columns(tmp_path):
    # Candidate construction needs decision-time stop inputs in addition to the
    # Strategy columns. The replay loader must not silently strip them.
    artifact = tmp_path / "strategy_ready.csv"
    frame = _rows()
    frame.to_csv(artifact, index=False)

    loaded = _load_input(artifact)

    assert "atr_14" in loaded.columns
    assert "support_20" in loaded.columns
    assert len(loaded) == len(frame)


def test_manifest_verification_fails_closed_on_tampered_artifact(tmp_path):
    artifact = tmp_path / "strategy_ready.csv"
    artifact.write_text(
        "timestamp,symbol\\n2026-09-21T10:00:00Z,TEST\\n",
        encoding="utf-8",
    )

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = tmp_path / "paper_dataset_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": "PAPER-DATASET-MANIFEST-v1",
                "dataset_version": "paper-test-v1",
                "artifact": {
                    "sha256": digest,
                    "rows": 1,
                    "symbols": ["TEST"],
                    "period_start": "2026-09-21T10:00:00+00:00",
                    "period_end": "2026-09-21T10:00:00+00:00",
                },
            }
        ),
        encoding="utf-8",
    )

    verified = _verify_manifest(artifact, manifest)
    provenance = _manifest_provenance(verified)
    assert provenance["dataset_version"] == "paper-test-v1"
    assert provenance["sha256"] == digest
    assert provenance["rows"] == 1
    assert provenance["symbols"] == ["TEST"]

    artifact.write_text(
        "timestamp,symbol\\n2026-09-21T10:05:00Z,TEST\\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SHA-256"):
        _verify_manifest(artifact, manifest)
