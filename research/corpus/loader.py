"""Load historical Research Bot documents into a validated corpus."""

from __future__ import annotations

from pathlib import Path

from research.corpus.schema import (
    HistoricalResearchCorpus,
    ResearchCorpusDocument,
    ResearchCorpusManifest,
)
from research.storage.jsonl import JsonlResearchStore


class HistoricalResearchCorpusLoader:
    """Load canonical ResearchDocument records from append-only JSONL.

    The loader is intentionally lossless for point-in-time timestamps:
    published_at and available_at are read from the stored document and are
    never replaced with load time.
    """

    def load(
        self,
        path: str | Path,
        *,
        manifest: ResearchCorpusManifest,
    ) -> HistoricalResearchCorpus:
        source_path = Path(path)
        documents = JsonlResearchStore(source_path).read()

        wrapped = tuple(
            ResearchCorpusDocument(
                document=document,
                dataset_id=manifest.dataset_id,
                dataset_version=manifest.version,
                source_reference=(
                    f"jsonl://{source_path.as_posix()}#{document.document_id}"
                ),
            )
            for document in documents
        )

        return HistoricalResearchCorpus.from_documents(manifest, wrapped)
