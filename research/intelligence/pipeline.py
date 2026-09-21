"""End-to-end deterministic Research Intelligence pipeline.

The pipeline owns orchestration only:
normalize -> point-in-time context -> evidence scoring -> Analysis contract.

It never creates orders, position sizing, risk approvals, or execution
instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from research.contracts import ResearchContext, ResearchDocument
from research.integration.analysis_contract import ResearchAnalysisContext
from research.integration.context import ResearchContextBuilder
from research.intelligence.model import (
    ResearchIntelligenceModel,
    ResearchIntelligenceResult,
)
from research.normalization.normalizer import DocumentNormalizer


@dataclass(frozen=True, slots=True)
class ResearchIntelligenceRun:
    """Complete output of one point-in-time research analysis run."""

    context: ResearchContext
    intelligence: ResearchIntelligenceResult
    analysis_context: ResearchAnalysisContext


class ResearchIntelligencePipeline:
    """Compose the existing research components without duplicating logic."""

    def __init__(
        self,
        *,
        normalizer: DocumentNormalizer | None = None,
        context_builder: ResearchContextBuilder | None = None,
        model: ResearchIntelligenceModel | None = None,
    ) -> None:
        self.normalizer = normalizer or DocumentNormalizer()
        self.context_builder = context_builder or ResearchContextBuilder()
        self.model = model or ResearchIntelligenceModel()

    def run(
        self,
        *,
        symbol: str,
        as_of: datetime,
        documents: tuple[ResearchDocument, ...] | list[ResearchDocument],
    ) -> ResearchIntelligenceRun:
        normalized = tuple(
            self.normalizer.normalize(document) for document in documents
        )
        context = self.context_builder.build(
            symbol=symbol,
            as_of=as_of,
            documents=normalized,
        )
        intelligence = self.model.score_context(context)
        analysis_context = ResearchAnalysisContext.from_context(
            context,
            intelligence,
        )
        return ResearchIntelligenceRun(
            context=context,
            intelligence=intelligence,
            analysis_context=analysis_context,
        )
