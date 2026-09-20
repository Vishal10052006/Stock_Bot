"""Point-in-time-safe evaluation for financial sentiment models."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Protocol, Sequence

from research.contracts import ResearchDocument, SentimentResult


_ALLOWED_LABELS = ("positive", "negative", "neutral")


@dataclass(frozen=True, slots=True)
class FinancialSentimentExample:
    """One labeled financial-text observation.

    The document is retained so the evaluation remains tied to the canonical
    ResearchDocument contract and its provenance/timestamps.
    """

    document: ResearchDocument
    gold_label: str

    def __post_init__(self) -> None:
        label = self.gold_label.strip().lower()
        if label not in _ALLOWED_LABELS:
            raise ValueError(
                f"gold_label must be one of {_ALLOWED_LABELS}, got {self.gold_label!r}"
            )
        object.__setattr__(self, "gold_label", label)


class FinancialSentimentModel(Protocol):
    model_version: str

    def analyze(self, document: ResearchDocument) -> SentimentResult:
        ...


@dataclass(frozen=True, slots=True)
class SentimentEvaluation:
    """Reproducible multiclass sentiment evaluation result."""

    model_version: str
    observations: int
    labels: tuple[str, ...]
    accuracy: float
    macro_f1: float
    per_class_f1: tuple[tuple[str, float], ...]
    confusion_matrix: tuple[tuple[int, ...], ...]
    mean_confidence: float

    def f1_for(self, label: str) -> float:
        normalized = label.strip().lower()
        for name, score in self.per_class_f1:
            if name == normalized:
                return score
        raise KeyError(normalized)


def evaluate_sentiment_model(
    model: FinancialSentimentModel,
    examples: Sequence[FinancialSentimentExample],
    *,
    labels: Sequence[str] = _ALLOWED_LABELS,
) -> SentimentEvaluation:
    """Evaluate a sentiment model without downloading or mutating model state."""
    if not examples:
        raise ValueError("examples must be non-empty")

    normalized_labels = tuple(dict.fromkeys(label.strip().lower() for label in labels))
    if not normalized_labels or any(label not in _ALLOWED_LABELS for label in normalized_labels):
        raise ValueError("labels must contain only positive, negative, and neutral")
    if len(normalized_labels) < 2:
        raise ValueError("at least two labels are required")

    predictions: list[str] = []
    confidences: list[float] = []

    for example in examples:
        result = model.analyze(example.document)
        prediction = result.label.strip().lower()
        if prediction not in normalized_labels:
            raise ValueError(
                f"model returned label {result.label!r} outside evaluation labels"
            )
        confidence = float(result.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("model confidence must be within [0, 1]")
        predictions.append(prediction)
        confidences.append(confidence)

    gold = [example.gold_label for example in examples]
    accuracy = sum(p == g for p, g in zip(predictions, gold)) / len(gold)

    per_class: list[tuple[str, float]] = []
    for label in normalized_labels:
        tp = sum(p == label and g == label for p, g in zip(predictions, gold))
        fp = sum(p == label and g != label for p, g in zip(predictions, gold))
        fn = sum(p != label and g == label for p, g in zip(predictions, gold))
        denominator = 2 * tp + fp + fn
        per_class.append((label, (2 * tp / denominator) if denominator else 0.0))

    macro_f1 = sum(score for _, score in per_class) / len(per_class)
    index = {label: i for i, label in enumerate(normalized_labels)}
    matrix = [[0 for _ in normalized_labels] for _ in normalized_labels]
    for actual, predicted in zip(gold, predictions):
        matrix[index[actual]][index[predicted]] += 1

    return SentimentEvaluation(
        model_version=model.model_version,
        observations=len(examples),
        labels=normalized_labels,
        accuracy=accuracy,
        macro_f1=macro_f1,
        per_class_f1=tuple(per_class),
        confusion_matrix=tuple(tuple(row) for row in matrix),
        mean_confidence=sum(confidences) / len(confidences),
    )
