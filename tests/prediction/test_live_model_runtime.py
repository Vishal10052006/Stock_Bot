"""Tests for live model runtime boundaries without network access."""

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
from ml.models.logistic import LogisticOutcomeModel
from ml.prediction.live_bundle import LivePredictionBundle, save_live_prediction_bundle, load_live_prediction_bundle
from ml.prediction.contracts import PredictionProvenance
from ml.preprocessing.pipeline import FeaturePreprocessor


def _fitted_components():
    from tests.test_analysis_prediction_integration import _training_frame

    X, y = _training_frame()
    preprocessor = FeaturePreprocessor()
    model = LogisticOutcomeModel()
    model.fit(preprocessor.fit_transform(X), y)
    return model, preprocessor


def test_local_upstox_master_resolves_equity_and_nifty50(tmp_path: Path):
    path = tmp_path / "NSE.json.gz"
    payload = [
        {
            "segment": "NSE_EQ",
            "instrument_type": "EQ",
            "trading_symbol": "RELIANCE",
            "instrument_key": "NSE_EQ|INE002A01018",
            "isin": "INE002A01018",
        }
    ]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)

    mapper = UpstoxInstrumentMapper.from_local_master(path)

    assert mapper.instrument_key("RELIANCE") == "NSE_EQ|INE002A01018"
    assert mapper.instrument_key("NIFTY50") == "NSE_INDEX|Nifty 50"


def test_local_upstox_master_rejects_ambiguous_symbol(tmp_path: Path):
    path = tmp_path / "NSE.json.gz"
    payload = [
        {
            "segment": "NSE_EQ",
            "instrument_type": "EQ",
            "trading_symbol": "ABC",
            "instrument_key": "NSE_EQ|ONE",
        },
        {
            "segment": "NSE_EQ",
            "instrument_type": "EQ",
            "trading_symbol": "ABC",
            "instrument_key": "NSE_EQ|TWO",
        },
    ]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)

    with pytest.raises(ValueError, match="ambiguous"):
        UpstoxInstrumentMapper.from_local_master(path)


def test_live_prediction_bundle_round_trip(tmp_path: Path):
    model, preprocessor = _fitted_components()
    provenance = PredictionProvenance(
        model_version="phase9-live-test",
        model_family="logistic",
        dataset_version="test-dataset",
        feature_version="test-features",
        target_version="test-target",
        code_version="test-code",
    )
    path = tmp_path / "bundle.pkl"

    manifest = save_live_prediction_bundle(
        path,
        model=model,
        preprocessor=preprocessor,
        provenance=provenance,
        created_at="2026-09-29T00:00:00Z",
    )
    bundle, loaded = load_live_prediction_bundle(
        path,
        expected_sha256=manifest.artifact_sha256,
    )

    assert isinstance(bundle, LivePredictionBundle)
    assert loaded.artifact_sha256 == manifest.artifact_sha256
    assert bundle.provenance.model_version == "phase9-live-test"
    assert bundle.model.is_fitted
    assert bundle.preprocessor.is_fitted
