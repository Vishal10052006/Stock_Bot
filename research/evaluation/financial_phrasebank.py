"""Financial PhraseBank benchmark dataset adapter.

This adapter reads the original Financial PhraseBank text format locally.
It is an NLP benchmark adapter, not a historical market-data source:
the public benchmark does not provide point-in-time publication/availability
timestamps for each sentence. Such timestamps must therefore never be
invented and this dataset must not be used as the Research Bot historical PIT
corpus.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from research.contracts import ResearchDocument
from research.evaluation.sentiment import FinancialSentimentExample

DATASET_ID = "financial_phrasebank"
DATASET_VERSION = "1.0.0"
SOURCE_REFERENCE = "https://huggingface.co/datasets/takala/financial_phrasebank"
SUPPORTED_CONFIGS = ("allagree", "75agree", "66agree", "50agree")


@dataclass(frozen=True, slots=True)
class FinancialPhraseBankExample:
    """Raw benchmark example before conversion to ResearchDocument."""

    sentence: str
    label: str


def load_financial_phrasebank(
    path: str | Path,
    *,
    agreement: str = "allagree",
    evaluation_time: datetime | None = None,
) -> tuple[FinancialSentimentExample, ...]:
    """Load one original Financial PhraseBank agreement configuration.

    Source files use one example per line in sentence@label format.
    evaluation_time is metadata for this NLP benchmark representation only;
    it is not a claimed publication or availability time.
    """
    if agreement not in SUPPORTED_CONFIGS:
        raise ValueError(
            f"agreement must be one of {SUPPORTED_CONFIGS}, got {agreement!r}"
        )

    timestamp = evaluation_time or datetime(2000, 1, 1, tzinfo=timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("evaluation_time must be timezone-aware")

    examples: list[FinancialSentimentExample] = []
    source_path = Path(path)

    with source_path.open("r", encoding="iso-8859-1") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.rstrip("\n\r")
            if not raw.strip():
                continue
            try:
                sentence, label = raw.rsplit("@", 1)
            except ValueError as exc:
                raise ValueError(
                    f"invalid Financial PhraseBank row at line {line_number}"
                ) from exc

            sentence = sentence.strip()
            label = label.strip().lower()
            if not sentence:
                raise ValueError(
                    f"empty sentence at Financial PhraseBank line {line_number}"
                )
            if label not in {"positive", "negative", "neutral"}:
                raise ValueError(
                    f"invalid sentiment label at line {line_number}: {label!r}"
                )

            document = ResearchDocument(
                document_id=f"{DATASET_ID}:{agreement}:{line_number}",
                source_id=DATASET_ID,
                external_id=f"{agreement}:{line_number}",
                title="Financial PhraseBank benchmark sentence",
                content=sentence,
                published_at=timestamp,
                observed_at=timestamp,
                processed_at=timestamp,
                available_at=timestamp,
                language="en",
                metadata={
                    "dataset_id": DATASET_ID,
                    "dataset_version": DATASET_VERSION,
                    "agreement": agreement,
                    "source_reference": SOURCE_REFERENCE,
                    "temporal_provenance": "benchmark_only",
                    "source_path": source_path.name,
                },
            )
            examples.append(FinancialSentimentExample(document, label))

    if not examples:
        raise ValueError("Financial PhraseBank file contains no examples")

    return tuple(examples)
