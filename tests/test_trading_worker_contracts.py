from pathlib import Path

import pandas as pd

from workers.sentiment_worker import SentimentWorker
from workers.strategy_worker import StrategyWorker
from workers.technical_worker import TechnicalWorker


def test_technical_worker_has_execute_contract():
    worker = TechnicalWorker()

    assert worker.name == "technical_worker"
    assert callable(worker.execute)


def test_sentiment_worker_has_execute_contract():
    worker = SentimentWorker()

    assert worker.name == "sentiment_worker"
    assert callable(worker.execute)


def test_strategy_worker_has_execute_contract():
    worker = StrategyWorker()

    assert worker.name == "strategy_worker"
    assert callable(worker.execute)


def test_technical_worker_has_no_random_dependency():
    source = Path("workers/technical_worker.py").read_text()

    assert "import random" not in source
    assert "random.choice" not in source
    assert "random.uniform" not in source
    assert "random.random" not in source


def test_sentiment_worker_has_no_random_dependency():
    source = Path("workers/sentiment_worker.py").read_text()

    assert "import random" not in source
    assert "random.choice" not in source
    assert "random.uniform" not in source
    assert "random.random" not in source


def test_technical_worker_does_not_invent_signal_without_market_data():
    worker = TechnicalWorker()

    result = worker.execute("analyze stock: RELIANCE")

    assert result["signal"] == "NO_SIGNAL"
    assert result["confidence"] is None
    assert result["success"] is False


def test_sentiment_worker_does_not_invent_signal_without_sentiment_data():
    worker = SentimentWorker()

    result = worker.execute("analyze news for RELIANCE")

    assert result["signal"] == "NO_SIGNAL"
    assert result["confidence"] is None
    assert result["success"] is False


def test_technical_worker_is_deterministic():
    worker = TechnicalWorker()

    features = pd.DataFrame(
        {
            "rsi_14": [55.0],
            "macd_histogram": [0.25],
            "roc_14": [1.2],
            "vwap_distance_pct": [0.4],
            "atr_normalized": [0.01],
            "rvol_20": [1.4],
            "price_ema_9_distance_pct": [0.3],
            "price_ema_20_distance_pct": [0.8],
            "price_ema_50_distance_pct": [1.5],
            "ema_9_20_distance_pct": [0.5],
            "ema_20_50_distance_pct": [0.7],
        }
    )

    first = worker.execute(features)
    second = worker.execute(features)

    assert first == second


def test_sentiment_worker_preserves_supplied_evidence():
    worker = SentimentWorker()

    sentiment = {
        "label": "positive",
        "source_count": 5,
    }

    result = worker.execute({"sentiment": sentiment})

    assert result["sentiment"] == sentiment
    assert result["signal"] == "NO_SIGNAL"
    assert result["success"] is True
