from datetime import datetime, timezone

from research.contracts import ResearchDocument
from research.evaluation import FinancialSentimentExample, evaluate_sentiment_model
from research.sentiment.finbert import FinBertSentiment


def _document(document_id: str, text: str = "Earnings update") -> ResearchDocument:
    available_at = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    return ResearchDocument(
        document_id=document_id,
        source_id="financial-source",
        external_id=document_id,
        title=text,
        content="Company reported results.",
        published_at=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=("ABC",),
    )


class FakePipeline:
    def __init__(self, label: str) -> None:
        self.label = label

    def __call__(self, text: str, **kwargs):
        probabilities = {
            "positive": 0.8 if self.label == "positive" else 0.1,
            "negative": 0.8 if self.label == "negative" else 0.1,
            "neutral": 0.8 if self.label == "neutral" else 0.1,
        }
        return [
            {"label": label, "score": score}
            for label, score in probabilities.items()
        ]


def test_finbert_adapter_satisfies_sentiment_evaluation_contract():
    model = FinBertSentiment(
        model_name="test-finbert",
        classifier=FakePipeline("positive"),
    )
    examples = [
        FinancialSentimentExample(_document("p"), "positive"),
        FinancialSentimentExample(_document("n"), "positive"),
    ]

    result = evaluate_sentiment_model(model, examples)

    assert result.model_version == "finbert:test-finbert"
    assert result.observations == 2
    assert result.accuracy == 1.0


def test_finbert_adapter_produces_probability_derived_score():
    model = FinBertSentiment(
        model_name="test-finbert",
        classifier=FakePipeline("negative"),
    )

    result = model.analyze(_document("n"))

    assert result.label == "negative"
    assert result.score == -0.7
    assert result.confidence == 0.8
