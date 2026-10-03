from __future__ import annotations

from pathlib import Path

import pytest

import trading.runtime_cli as runtime_cli
from trading.runtime_cli import RuntimeConfig, RuntimeMode


def test_v1_live_review_cli_routes_to_manual_runtime_without_paper_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured = {}

    def fake_run_live_manual_review(config):
        captured["config"] = config
        return 0

    monkeypatch.setattr(
        runtime_cli,
        "run_live_manual_review",
        fake_run_live_manual_review,
    )

    config = RuntimeConfig(
        mode=RuntimeMode.LIVE_MANUAL_REVIEW,
        symbol="RELIANCE",
        benchmark_symbol="NIFTY50",
        model_artifact=tmp_path / "phase9.joblib",
        model_sha256="a" * 64,
        model_version="phase9-logistic-v1",
        data_version="upstox-live-v1",
        feature_version="features-v1",
        max_candles=1,
        operator_snapshot_path=tmp_path / "operator_snapshot.json",
    )

    assert runtime_cli.dispatch(config) == 0

    review_config = captured["config"]
    assert review_config.symbol == "RELIANCE"
    assert review_config.benchmark_symbol == "NIFTY50"
    assert review_config.model_version == "phase9-logistic-v1"
    assert review_config.data_version == "upstox-live-v1"
    assert review_config.feature_version == "features-v1"
    assert review_config.max_candles == 1
    assert review_config.operator_snapshot_path == tmp_path / "operator_snapshot.json"
    assert not hasattr(review_config, "initial_equity")


def test_v1_live_review_cli_requires_explicit_runtime_identity(tmp_path: Path) -> None:
    base = dict(
        mode=RuntimeMode.LIVE_MANUAL_REVIEW,
        symbol="RELIANCE",
        benchmark_symbol="NIFTY50",
        model_artifact=tmp_path / "phase9.joblib",
        model_sha256="a" * 64,
        model_version="phase9-logistic-v1",
    )

    with pytest.raises(ValueError, match="data_version"):
        runtime_cli.dispatch(
            RuntimeConfig(**base, data_version="", feature_version="features-v1")
        )

    with pytest.raises(ValueError, match="feature_version"):
        runtime_cli.dispatch(
            RuntimeConfig(**base, data_version="upstox-live-v1", feature_version="")
        )
