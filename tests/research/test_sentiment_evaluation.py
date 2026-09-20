from datetime import datetime, timezone

import pytest

from research.contracts import ResearchDocument, SentimentResult
from research.evaluation import FinancialSentimentExample, evaluate_sentiment_model


def _document(document_id: str) -> ResearchDocument:
    available_at = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    return ResearchDocument(
        document_id=document_id,
        source_id="source-a",
        external_id=document_id,
        title=document_id,
        content="financial text",
        published_at=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=("ABC",),
    )


class FakeSentimentModel:
    model_version = "fake-1.0"

    def analyze(self, document: ResearchDocument) -> SentimentResult:
        labels = {
            "p": ("positive", 0.9),
            "n": ("negative", 0.8),
            "u": ("neutral", 0.7),
            "wrong": ("negative", 0.6),
        }
        label, confidence = labels[document.document_id]
        return SentimentResult(
            label=label,
            score=0.0,
            confidence=confidence,
            model_version=self.model_version,
        )


def test_evaluation_reports_multiclass_metrics():
    examples = [
        FinancialSentimentExample(_document("p"), "positive"),
        FinancialSentimentExample(_document("n"), "negative"),
        FinancialSentimentExample(_document("u"), "neutral"),
        FinancialSentimentExample(_document("wrong"), "positive"),
    ]

    result = evaluate_sentiment_model(FakeSentimentModel(), examples)

    assert result.observations == 4
    assert result.accuracy == pytest.approx(0.75)
    assert result.macro_f1 == pytest.approx((2 / 3 + 1.0 + 1.0) / 3)
    assert result.confusion_matrix == (
        (1, 1, 0),
        (0, 1, 0),
        (0, 0, 1),
    )
    assert result.mean_confidence == pytest.approx(0.75)
    assert result.f1_for("positive") == pytest.approx(2 / 3)


def test_example_normalizes_gold_label():
    example = FinancialSentimentExample(_document("p"), " POSITIVE ")
    assert example.gold_label == "positive"


def test_rejects_unknown_gold_label():
    with pytest.raises(ValueError, match="gold_label"):
        FinancialSentimentExample(_document("p"), "bullish")


def test_rejects_model_label_outside_evaluation_set():
    class BadModel(FakeSentimentModel):
        def analyze(self, document: ResearchDocument) -> SentimentResult:
            return SentimentResult(
                label="bullish",
                score=1.0,
                confidence=1.0,
                model_version=self.model_version,
            )

    examples = [FinancialSentimentExample(_document("p"), "positive")]
    with pytest.raises(ValueError, match="outside evaluation labels"):
        evaluate_sentiment_model(BadModel(), examples)


def test_rejects_invalid_confidence():
    class BadModel(FakeSentimentModel):
        def analyze(self, document: ResearchDocument) -> SentimentResult:
            return SentimentResult(
                label="positive",
                score=1.0,
                confidence=1.5,
                model_version=self.model_version,
            )

    examples = [FinancialSentimentExample(_document("p"), "positive")]
    with pytest.raises(ValueError, match="confidence"):
        evaluate_sentiment_model(BadModel(), examples)
