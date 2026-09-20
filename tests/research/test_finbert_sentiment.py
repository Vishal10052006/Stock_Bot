"""Tests for the optional FinBERT sentiment adapter."""

from datetime import datetime, timezone

from research.contracts import ResearchDocument
from research.sentiment.finbert import FinBertSentiment

UTC = timezone.utc


def document() -> ResearchDocument:
    now = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    return ResearchDocument(
        document_id="finbert-test",
        source_id="test",
        external_id="finbert-test",
        title="RELIANCE earnings",
        content="profit growth exceeded expectations",
        published_at=now,
        observed_at=now,
        processed_at=now,
        available_at=now,
        symbols=("RELIANCE",),
    )


class FakeClassifier:
    def __call__(self, text, **kwargs):
        assert text
        assert kwargs["truncation"] is True
        assert kwargs["max_length"] == 512
        return [
            {"label": "positive", "score": 0.85},
            {"label": "negative", "score": 0.05},
            {"label": "neutral", "score": 0.10},
        ]


def test_finbert_adapter_maps_probabilities_to_signed_score():
    model = FinBertSentiment(
        model_name="test-finbert",
        classifier=FakeClassifier(),
    )
    result = model.analyze(document())

    assert result.label == "positive"
    assert result.score == 0.80
    assert result.confidence == 0.85
    assert result.model_version == "finbert:test-finbert"


class LegacyFakeClassifier:
    def __call__(self, text, **kwargs):
        if "top_k" in kwargs:
            raise TypeError("legacy pipeline")
        return [[
            {"label": "positive", "score": 0.20},
            {"label": "negative", "score": 0.70},
            {"label": "neutral", "score": 0.10},
        ]]


def test_finbert_adapter_supports_legacy_pipeline_shape():
    model = FinBertSentiment(
        model_name="legacy-test",
        classifier=LegacyFakeClassifier(),
    )
    result = model.analyze(document())

    assert result.label == "negative"
    assert result.score == -0.50
