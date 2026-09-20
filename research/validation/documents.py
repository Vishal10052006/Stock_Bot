"""Research-document validation and provenance checks."""
from __future__ import annotations

from collections.abc import Iterable
from research.contracts import ResearchDocument


def validate_document(document: ResearchDocument) -> None:
    if not document.document_id or not document.source_id:
        raise ValueError("document_id and source_id are required")
    if not document.title.strip():
        raise ValueError("research document title cannot be empty")
    if not document.content.strip():
        raise ValueError("research document content cannot be empty")
    if document.available_at < document.observed_at:
        raise ValueError("available_at must be >= observed_at")


def validate_documents(documents: Iterable[ResearchDocument]) -> None:
    seen: set[tuple[str, str]] = set()
    for document in documents:
        validate_document(document)
        key = (document.source_id, document.external_id)
        if key in seen:
            raise ValueError(f"duplicate provider document: {key}")
        seen.add(key)
