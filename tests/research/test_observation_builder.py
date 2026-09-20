from datetime import datetime, timedelta, timezone

import pytest

from market.candles.models import Candle
from research.contracts import ResearchDocument, SentimentResult
from research.evaluation.observation_builder import (
    build_research_market_observations,
    to_evaluation_observations,
)

UTC = timezone.utc
T0 = datetime(2026, 9, 20, 9, 15, tzinfo=UTC)


class FakeSentiment:
    model_version = "fake:research-observation"

    def analyze(self, document):
        return SentimentResult(
            label="positive",
            score=0.8,
            confidence=1.0,
            model_version=self.model_version,
        )


def make_doc(*, available_at, document_id=None, content="earnings increased"):
    minute_id = int((available_at - T0).total_seconds() // 60)
    return ResearchDocument(
        document_id=document_id or f"doc-{minute_id}",
        source_id="test-source",
        external_id=f"x-{minute_id}",
        title="Test",
        content=content,
        published_at=available_at - timedelta(minutes=1),
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=("ABC",),
    )


def make_candle(timestamp, close):
    return Candle(
        symbol="ABC",
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=timestamp,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000.0,
    )


def test_builder_uses_only_research_available_at_decision_close():
    candles = tuple(
        make_candle(T0 + timedelta(minutes=5 * i), 100.0 + i)
        for i in range(13)
    )
    docs = (
        make_doc(available_at=T0 + timedelta(minutes=4), document_id="doc-4"),
        make_doc(available_at=T0 + timedelta(minutes=11), document_id="doc-11"),
    )

    rows = build_research_market_observations(
        symbol="ABC",
        candles=candles,
        documents=docs,
        horizons_minutes=(10,),
        context_builder=__import__(
            "research.integration.context",
            fromlist=["ResearchContextBuilder"],
        ).ResearchContextBuilder(sentiment=FakeSentiment()),
        require_evidence=True,
    )

    # First decision is 09:20: only the 09:19 document can contribute.
    first = rows[0]
    assert first.decision_time == T0 + timedelta(minutes=5)
    assert first.feature_available_at == T0 + timedelta(minutes=4)
    assert first.source_document_ids == ("doc-19",)
    assert first.outcome_timestamp == T0 + timedelta(minutes=15)


def test_builder_requires_exact_future_candle_and_uses_close_to_close_return():
    candles = (
        make_candle(T0, 100.0),
        make_candle(T0 + timedelta(minutes=5), 101.0),
        make_candle(T0 + timedelta(minutes=10), 102.0),
        make_candle(T0 + timedelta(minutes=15), 103.0),
    )
    docs = (make_doc(available_at=T0, document_id="doc-0"),)

    rows = build_research_market_observations(
        symbol="ABC",
        candles=candles,
        documents=docs,
        horizons_minutes=(10,),
        context_builder=__import__(
            "research.integration.context",
            fromlist=["ResearchContextBuilder"],
        ).ResearchContextBuilder(sentiment=FakeSentiment()),
    )

    assert len(rows) == 2
    assert rows[0].decision_time == T0 + timedelta(minutes=5)
    assert rows[0].decision_close == 101.0
    assert rows[0].outcome_close == 103.0
    assert rows[0].forward_return == pytest.approx(103.0 / 101.0 - 1.0)


def test_future_document_never_enters_context():
    candles = (
        make_candle(T0, 100.0),
        make_candle(T0 + timedelta(minutes=5), 101.0),
        make_candle(T0 + timedelta(minutes=10), 102.0),
    )
    future_doc = make_doc(available_at=T0 + timedelta(minutes=7), document_id="doc-7")

    rows = build_research_market_observations(
        symbol="ABC",
        candles=candles,
        documents=(future_doc,),
        horizons_minutes=(5,),
        context_builder=__import__(
            "research.integration.context",
            fromlist=["ResearchContextBuilder"],
        ).ResearchContextBuilder(sentiment=FakeSentiment()),
        require_evidence=True,
    )

    assert len(rows) == 1
    assert rows[0].decision_time == T0 + timedelta(minutes=15)
    assert rows[0].source_document_ids == ("doc-7",)


def test_conversion_preserves_causal_contract():
    candles = (
        make_candle(T0, 100.0),
        make_candle(T0 + timedelta(minutes=5), 101.0),
    )
    docs = (make_doc(available_at=T0, document_id="doc-0"),)

    rows = build_research_market_observations(
        symbol="ABC",
        candles=candles,
        documents=docs,
        horizons_minutes=(5,),
        context_builder=__import__(
            "research.integration.context",
            fromlist=["ResearchContextBuilder"],
        ).ResearchContextBuilder(sentiment=FakeSentiment()),
    )
    converted = to_evaluation_observations(rows)

    assert len(converted) == 1
    assert converted[0].outcome_timestamp > converted[0].decision_time
