"""Historical Research Bot corpus contracts and builders."""

from research.corpus.adapter import archive_record_to_document
from research.corpus.archive import HISTORICAL_ARCHIVE_SCHEMA_VERSION, HistoricalArchiveRecord
from research.corpus.archive_jsonl import HistoricalArchiveJsonlLoader
from research.corpus.builder import HistoricalCorpusBuildAudit, HistoricalResearchCorpusBuilder
from research.corpus.intake import HistoricalIntakeResult, ingest_nse_csv
from research.corpus.loader import HistoricalResearchCorpusLoader
from research.corpus.nse_archive import NSEHistoricalArchiveClient
from research.corpus.schema import (
    CORPUS_SCHEMA_VERSION,
    HistoricalResearchCorpus,
    ResearchCorpusDocument,
    ResearchCorpusManifest,
)

__all__ = [
    "CORPUS_SCHEMA_VERSION",
    "HISTORICAL_ARCHIVE_SCHEMA_VERSION",
    "archive_record_to_document",
    "HistoricalArchiveRecord",
    "HistoricalArchiveJsonlLoader",
    "HistoricalCorpusBuildAudit",
    "HistoricalResearchCorpus",
    "HistoricalResearchCorpusBuilder",
    "HistoricalResearchCorpusLoader",
    "HistoricalIntakeResult",
    "ingest_nse_csv",
    "NSEHistoricalArchiveClient",
    "ResearchCorpusDocument",
    "ResearchCorpusManifest",
]
