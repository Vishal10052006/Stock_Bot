"""Research NLP evaluation contracts and datasets."""

from research.evaluation.financial_phrasebank import (
    DATASET_ID,
    DATASET_VERSION,
    SOURCE_REFERENCE,
    SUPPORTED_CONFIGS,
    load_financial_phrasebank,
)
from research.evaluation.sentiment import (
    FinancialSentimentExample,
    SentimentEvaluation,
    evaluate_sentiment_model,
)

__all__ = [
    "DATASET_ID",
    "DATASET_VERSION",
    "SOURCE_REFERENCE",
    "SUPPORTED_CONFIGS",
    "FinancialSentimentExample",
    "SentimentEvaluation",
    "evaluate_sentiment_model",
    "load_financial_phrasebank",
]
