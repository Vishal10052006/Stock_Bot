from datetime import datetime, timezone

from research.contracts import ResearchDocument
from research.corpus import (
    HistoricalResearchCorpus,
    ResearchCorpusDocument,
    ResearchCorpusManifest,
)


def _document(document_id: str, content: str = "Profit growth was strong.") -> ResearchDocument:
    available_at = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    return ResearchDocument(
        document_id=document_id,
        source_id="source-a",
        external_id=document_id,
        title="Earnings update",
        content=content,
        published_at=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=("ABC",),
    )


def _manifest(count: int) -> ResearchCorpusManifest:
    return ResearchCorpusManifest(
        dataset_id="financial-news",
        version="2026-01",
        source="test-fixture",
        accessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        document_count=count,
    )


def _item(document: ResearchDocument) -> ResearchCorpusDocument:
    return ResearchCorpusDocument(
        document=document,
        dataset_id="financial-news",
        dataset_version="2026-01",
        source_reference=f"fixture://{document.document_id}",
    )


def test_manifest_has_explicit_schema_version():
    manifest = _manifest(1)

    assert manifest.schema_version == "1.0"


def test_fingerprint_is_stable_when_document_order_changes():
    first = _item(_document("doc-1"))
    second = _item(_document("doc-2"))

    corpus_a = HistoricalResearchCorpus.from_documents(
        _manifest(2),
        [first, second],
    )
    corpus_b = HistoricalResearchCorpus.from_documents(
        _manifest(2),
        [second, first],
    )

    assert corpus_a.fingerprint == corpus_b.fingerprint
    assert len(corpus_a.fingerprint) == 64


def test_fingerprint_changes_when_document_content_changes():
    corpus_a = HistoricalResearchCorpus.from_documents(
        _manifest(1),
        [_item(_document("doc-1", "Profit growth was strong."))],
    )
    corpus_b = HistoricalResearchCorpus.from_documents(
        _manifest(1),
        [_item(_document("doc-1", "Profit growth declined."))],
    )

    assert corpus_a.fingerprint != corpus_b.fingerprint


def test_fingerprint_is_independent_of_source_reference_path():
    document = _document("doc-1")
    first = ResearchCorpusDocument(
        document=document,
        dataset_id="financial-news",
        dataset_version="2026-01",
        source_reference="jsonl:///tmp/a/doc-1",
    )
    second = ResearchCorpusDocument(
        document=document,
        dataset_id="financial-news",
        dataset_version="2026-01",
        source_reference="jsonl:///home/user/other/doc-1",
    )

    corpus_a = HistoricalResearchCorpus.from_documents(_manifest(1), [first])
    corpus_b = HistoricalResearchCorpus.from_documents(_manifest(1), [second])

    assert corpus_a.fingerprint == corpus_b.fingerprint
