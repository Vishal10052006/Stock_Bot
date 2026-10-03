from __future__ import annotations

from pathlib import Path

import pytest

from trading.live.manual_review_runtime import LiveManualReviewConfig


def test_manual_review_runtime_has_no_virtual_account_configuration() -> None:
    source = Path(
        "trading/live/manual_review_runtime.py"
    ).read_text(encoding="utf-8")

    assert "initial_equity" not in source
    assert "VirtualIntradaySession" not in source
    assert "LivePaperEngine" not in source
    assert "MANUAL BUY/SELL ONLY" in source
    assert "paper_engine=None" in source


def test_manual_review_config_requires_explicit_versions_and_model_identity() -> None:
    with pytest.raises(ValueError, match="data_version"):
        LiveManualReviewConfig(
            symbol="RELIANCE",
            benchmark_symbol="NIFTY50",
            model_artifact=Path("model.joblib"),
            model_sha256="0" * 64,
            model_version="model-v1",
            data_version="",
            feature_version="feature-v1",
        )

    with pytest.raises(ValueError, match="feature_version"):
        LiveManualReviewConfig(
            symbol="RELIANCE",
            benchmark_symbol="NIFTY50",
            model_artifact=Path("model.joblib"),
            model_sha256="0" * 64,
            model_version="model-v1",
            data_version="data-v1",
            feature_version="",
        )


def test_manual_review_config_accepts_explicit_runtime_identity() -> None:
    config = LiveManualReviewConfig(
        symbol="RELIANCE",
        benchmark_symbol="NIFTY50",
        model_artifact=Path("model.joblib"),
        model_sha256="0" * 64,
        model_version="model-v1",
        data_version="data-v1",
        feature_version="feature-v1",
        max_candles=1,
    )

    assert config.symbol == "RELIANCE"
    assert config.benchmark_symbol == "NIFTY50"
    assert config.max_candles == 1
