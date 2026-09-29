"""Live paper session-control regression tests."""

import pytest

from ml.prediction.live_runtime import LiveModelRuntimeConfig


def test_live_runtime_defaults_to_ten_paper_trades():
    config = LiveModelRuntimeConfig()
    assert config.target_trades == 10
    assert config.max_predictions == 500


def test_live_runtime_rejects_invalid_trade_target():
    with pytest.raises(ValueError, match="target_trades"):
        LiveModelRuntimeConfig(target_trades=0)
