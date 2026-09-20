from datetime import datetime, timezone

from research.contracts import ResearchDocument
from research.corpus import HistoricalResearchCorpusLoader, ResearchCorpusManifest
from research.storage.jsonl import JsonlResearchStore


def _document() -> ResearchDocument:
    available_at = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    return ResearchDocument(
        document_id="doc-1",
        source_id="source-a",
        external_id="external-1",
        title="Earnings update",
        content="Profit growth was strong.",
        published_at=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        observed_at=available_at,
        processed_at=available_at,
        available_at=available_at,
        symbols=("ABC",),
    )


def test_loader_preserves_point_in_time_fields(tmp_path):
    path = tmp_path / "historical.jsonl"
    document = _document()
    JsonlResearchStore(path).append(document)

    manifest = ResearchCorpusManifest(
        dataset_id="financial-news",
        version="2026-01",
        source="test-fixture",
        accessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        document_count=1,
    )

    corpus = HistoricalResearchCorpusLoader().load(path, manifest=manifest)

    loaded = corpus.documents[0]
    assert loaded.document.available_at == document.available_at
    assert loaded.document.published_at == document.published_at
    assert loaded.dataset_id == "financial-news"
    assert loaded.dataset_version == "2026-01"
    assert loaded.source_reference.endswith("#doc-1")


def test_loader_rejects_manifest_count_mismatch(tmp_path):
    path = tmp_path / "historical.jsonl"
    JsonlResearchStore(path).append(_document())

    manifest = ResearchCorpusManifest(
        dataset_id="financial-news",
        version="2026-01",
        source="test-fixture",
        accessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        document_count=2,
    )

    try:
        HistoricalResearchCorpusLoader().load(path, manifest=manifest)
    except ValueError as exc:
        assert "document_count" in str(exc)
    else:
        raise AssertionError("expected manifest count mismatch")
