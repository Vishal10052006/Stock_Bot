"""Research NLP evaluation contracts and datasets."""

from research.evaluation.benchmark import (
    FinancialPhraseBankBenchmark,
    run_financial_phrasebank_benchmark,
    run_finbert_phrasebank_benchmark,
)
from research.evaluation.intelligence import (
    ResearchEvaluationObservation,
    ResearchOutcomeEvaluation,
    evaluate_research_outcomes,
)
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
    "ResearchEvaluationObservation",
    "ResearchOutcomeEvaluation",
    "evaluate_research_outcomes",
    "FinancialPhraseBankBenchmark",
    "run_financial_phrasebank_benchmark",
    "run_finbert_phrasebank_benchmark",
    "DATASET_ID",
    "DATASET_VERSION",
    "SOURCE_REFERENCE",
    "SUPPORTED_CONFIGS",
    "FinancialSentimentExample",
    "SentimentEvaluation",
    "evaluate_sentiment_model",
    "load_financial_phrasebank",
]
