"""Reproducible Financial PhraseBank sentiment benchmark runner.

This module evaluates a FinancialSentimentModel on the local Financial
PhraseBank benchmark. It reports NLP classification metrics only; it does
not infer trading performance, expected returns, or predictive market edge.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from research.evaluation.financial_phrasebank import (
    DATASET_ID,
    DATASET_VERSION,
    SOURCE_REFERENCE,
    load_financial_phrasebank,
)
from research.evaluation.sentiment import (
    FinancialSentimentModel,
    SentimentEvaluation,
    evaluate_sentiment_model,
)


@dataclass(frozen=True, slots=True)
class FinancialPhraseBankBenchmark:
    """Serializable benchmark result with dataset provenance."""

    dataset_id: str
    dataset_version: str
    agreement: str
    source_reference: str
    dataset_path: str
    model_version: str
    observations: int
    labels: tuple[str, ...]
    accuracy: float
    macro_f1: float
    per_class_f1: tuple[tuple[str, float], ...]
    confusion_matrix: tuple[tuple[int, ...], ...]
    mean_confidence: float

    @classmethod
    def from_evaluation(
        cls,
        evaluation: SentimentEvaluation,
        *,
        agreement: str,
        dataset_path: str | Path,
    ) -> "FinancialPhraseBankBenchmark":
        return cls(
            dataset_id=DATASET_ID,
            dataset_version=DATASET_VERSION,
            agreement=agreement,
            source_reference=SOURCE_REFERENCE,
            dataset_path=str(Path(dataset_path)),
            model_version=evaluation.model_version,
            observations=evaluation.observations,
            labels=evaluation.labels,
            accuracy=evaluation.accuracy,
            macro_f1=evaluation.macro_f1,
            per_class_f1=evaluation.per_class_f1,
            confusion_matrix=evaluation.confusion_matrix,
            mean_confidence=evaluation.mean_confidence,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_financial_phrasebank_benchmark(
    dataset_path: str | Path,
    model: FinancialSentimentModel,
    *,
    agreement: str = "allagree",
    evaluation_time: datetime | None = None,
) -> FinancialPhraseBankBenchmark:
    """Run one deterministic benchmark configuration on a local dataset file."""
    examples = load_financial_phrasebank(
        dataset_path,
        agreement=agreement,
        evaluation_time=evaluation_time,
    )
    evaluation = evaluate_sentiment_model(model, examples)
    return FinancialPhraseBankBenchmark.from_evaluation(
        evaluation,
        agreement=agreement,
        dataset_path=dataset_path,
    )


def run_finbert_phrasebank_benchmark(
    dataset_path: str | Path,
    *,
    agreement: str = "allagree",
    evaluation_time: datetime | None = None,
    model_name: str = "ProsusAI/finbert",
) -> FinancialPhraseBankBenchmark:
    """Run the benchmark using the explicit FinBERT adapter.

    Model weights/tokenizer are loaded by the FinBertSentiment adapter. This
    function never claims that benchmark performance translates to trading
    performance.
    """
    from research.sentiment.finbert import FinBertSentiment

    model = FinBertSentiment(model_name=model_name)
    return run_financial_phrasebank_benchmark(
        dataset_path,
        model,
        agreement=agreement,
        evaluation_time=evaluation_time,
    )
