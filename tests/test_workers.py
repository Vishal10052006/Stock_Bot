"""
Tests for the Stock Bot worker contracts.
"""

from workers.base_worker import BaseWorker
from workers.sentiment_worker import SentimentWorker
from workers.strategy_worker import StrategyWorker
from workers.technical_worker import TechnicalWorker


def test_base_worker_requires_execute():
    """BaseWorker should expose the execution contract."""

    worker = BaseWorker()

    try:
        worker.execute("test task")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("BaseWorker.execute() must raise NotImplementedError")


def test_technical_worker_implements_execute():
    """TechnicalWorker should implement execute()."""

    worker = TechnicalWorker()

    assert callable(worker.execute)


def test_sentiment_worker_implements_execute():
    """SentimentWorker should implement execute()."""

    worker = SentimentWorker()

    assert callable(worker.execute)


def test_strategy_worker_implements_execute():
    """StrategyWorker should implement execute()."""

    worker = StrategyWorker()

    assert callable(worker.execute)
