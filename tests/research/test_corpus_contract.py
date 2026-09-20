from datetime import datetime, timezone

import pytest

from research.contracts import ResearchDocument
from research.corpus import (
    HistoricalResearchCorpus,
    ResearchCorpusDocument,
    ResearchCorpusManifest,
)


def _document(
    document_id: str = "doc-1",
    *,
    published_at: datetime | None = None,
    available_at: datetime | None = None,
) -> ResearchDocument:
    published_at = published_at or datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    available_at = available_at or datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    return ResearchDocument(
        document_id=document_id,
        source_id="source-a",
        external_id=document_id,
        title="Earnings update",
        content="Profit growth was strong.",
        published_at=published_at,
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=("ABC",),
    )


def _manifest(count: int = 1) -> ResearchCorpusManifest:
    return ResearchCorpusManifest(
        dataset_id="financial-news",
        version="2026-01",
        source="test-fixture",
        accessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        time_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        time_end=datetime(2026, 1, 31, 23, 59, tzinfo=timezone.utc),
        document_count=count,
    )


def _item(document: ResearchDocument) -> ResearchCorpusDocument:
    return ResearchCorpusDocument(
        document=document,
        dataset_id="financial-news",
        dataset_version="2026-01",
        source_reference="fixture://financial-news/doc-1",
    )


def test_valid_corpus_preserves_point_in_time_timestamps():
    document = _document()
    corpus = HistoricalResearchCorpus.from_documents(_manifest(), [_item(document)])

    assert corpus.document_count == 1
    assert corpus.symbols == ("ABC",)
    assert corpus.documents[0].document.available_at == document.available_at


def test_rejects_duplicate_document_ids():
    first = _item(_document("doc-1"))
    second = _item(_document("doc-1"))

    with pytest.raises(ValueError, match="duplicate document_id"):
        HistoricalResearchCorpus.from_documents(_manifest(2), [first, second])


def test_rejects_dataset_identity_mismatch():
    item = ResearchCorpusDocument(
        document=_document(),
        dataset_id="other-dataset",
        dataset_version="2026-01",
        source_reference="fixture://other/doc-1",
    )

    with pytest.raises(ValueError, match="dataset_id"):
        HistoricalResearchCorpus.from_documents(_manifest(), [item])


def test_rejects_manifest_count_mismatch():
    with pytest.raises(ValueError, match="document_count"):
        HistoricalResearchCorpus.from_documents(_manifest(2), [_item(_document())])


def test_rejects_document_outside_manifest_window():
    document = _document(
        published_at=datetime(2025, 12, 31, 23, tzinfo=timezone.utc),
        available_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="time_start"):
        HistoricalResearchCorpus.from_documents(_manifest(), [_item(document)])
