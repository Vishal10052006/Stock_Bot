from datetime import datetime, timezone

from research.contracts import ResearchDocument
from research.corpus.builder import HistoricalCorpusBuildAudit
from research.corpus.schema import (
    HistoricalResearchCorpus,
    ResearchCorpusDocument,
    ResearchCorpusManifest,
)
from research.monitoring.production_check import run_production_check

UTC = timezone.utc


def test_production_check_passes_structural_corpus():
    now = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    document = ResearchDocument(
        document_id="doc-1",
        source_id="nse-corporate-filings",
        external_id="x-1",
        title="Results",
        content="Revenue increased",
        published_at=now,
        observed_at=now,
        processed_at=now,
        available_at=now,
        symbols=("ABC",),
    )
    manifest = ResearchCorpusManifest(
        dataset_id="test",
        version="1",
        source="nse",
        accessed_at=now,
        document_count=1,
    )
    corpus = HistoricalResearchCorpus.from_documents(
        manifest,
        (ResearchCorpusDocument(
            document=document,
            dataset_id="test",
            dataset_version="1",
            source_reference="nse",
        ),),
    )
    audit = HistoricalCorpusBuildAudit(
        input_documents=1,
        accepted_documents=1,
        duplicate_documents=0,
        rejected_documents=0,
        rejected_document_ids=(),
        symbols_requested=(),
        time_start=None,
        time_end=None,
    )

    result = run_production_check(
        corpus,
        audit,
        required_sources=("nse-corporate-filings",),
        evaluated_oos_folds=1,
    )

    assert result.passed
    assert result.status == "PASS"
    assert not result.failures
