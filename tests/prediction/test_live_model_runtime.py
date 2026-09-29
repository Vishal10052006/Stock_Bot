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

def test_live_runtime_reports_silent_feed_exit_before_prediction():
    from threading import Event
    from types import SimpleNamespace

    class EmptyFeed:
        def __init__(self):
            self.started = False
            self.stopped = False

        def start(self, symbols):
            self.started = True

        def run(self):
            return iter(())

        def stop(self):
            self.stopped = True

    from ml.prediction.live_runtime import LiveModelRuntime

    runtime = object.__new__(LiveModelRuntime)
    runtime.config = SimpleNamespace(symbol="RELIANCE", benchmark="NIFTY50", max_predictions=500)
    runtime.feed = EmptyFeed()
    runtime.paper_engine = SimpleNamespace(
        session_completed=False,
        finalize_session=lambda: None,
    )
    runtime._pause_event = Event()
    runtime._pause_event.set()
    runtime._stop_requested = Event()
    runtime._kill_requested = Event()
    runtime.predictions = 0
    runtime.last_prediction = None
    runtime.paper_result = None
    runtime.benchmark_history = pd.DataFrame()
    runtime.target_history = pd.DataFrame()
    runtime.lifecycle_state = "CREATED"
    runtime.lifecycle_error = None
    runtime.benchmark_candles = 0
    runtime.target_candles = 0
    runtime.warmup = lambda: setattr(runtime, "lifecycle_state", "WARMUP_COMPLETED")

    with pytest.raises(RuntimeError, match="FEED_ENDED_BEFORE_FIRST_TARGET_CANDLE"):
        runtime.run()

    assert runtime.lifecycle_state == "FAILED"
    assert runtime.lifecycle_error == "FEED_ENDED_BEFORE_FIRST_TARGET_CANDLE"
    assert runtime.predictions == 0
    assert runtime.feed.started is True
    assert runtime.feed.stopped is True
