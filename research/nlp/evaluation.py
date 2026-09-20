"""Evaluation protocol for replacing the lexical NLP baseline."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence
from research.contracts import ResearchDocument


class ResearchTextModel(Protocol):
    model_version: str

    def score(self, document: ResearchDocument) -> float:
        """Return a deterministic sentiment/context score for one document."""
        ...


@dataclass(frozen=True, slots=True)
class TextModelEvaluation:
    model_version: str
    observations: int
    mean_absolute_error: float
    agreement_rate: float


def evaluate_text_model(model: ResearchTextModel, documents: Sequence[ResearchDocument],
                        reference_scores: Sequence[float], tolerance: float = 0.2) -> TextModelEvaluation:
    if len(documents) != len(reference_scores) or not documents:
        raise ValueError("documents and reference_scores must have equal non-zero length")
    predictions = [float(model.score(document)) for document in documents]
    errors = [abs(p - r) for p, r in zip(predictions, reference_scores)]
    agreement = sum(error <= tolerance for error in errors) / len(errors)
    return TextModelEvaluation(
        model_version=model.model_version,
        observations=len(documents),
        mean_absolute_error=sum(errors) / len(errors),
        agreement_rate=agreement,
    )
