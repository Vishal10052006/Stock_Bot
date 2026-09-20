"""Build point-in-time research rows from archived documents."""
from __future__ import annotations
from datetime import datetime
from research.contracts import ResearchDocument
from research.features.builder import ResearchFeatureBuilder
from research.causal.availability import filter_point_in_time
from research.datasets.schema import ResearchDatasetRow


class ResearchDatasetBuilder:
    def __init__(self, feature_builder: ResearchFeatureBuilder | None = None) -> None:
        self.feature_builder = feature_builder or ResearchFeatureBuilder()

    def build_row(self, *, symbol: str, decision_time: datetime,
                  documents: tuple[ResearchDocument, ...], dataset_version: str,
                  label: str | None = None, label_available_at: datetime | None = None) -> ResearchDatasetRow:
        eligible = tuple(d for d in filter_point_in_time(documents, decision_time) if symbol in d.symbols)
        features = self.feature_builder.build(eligible, symbol=symbol, decision_time=decision_time)
        available_at = max((d.available_at for d in eligible), default=decision_time)
        row = ResearchDatasetRow(
            dataset_version=dataset_version,
            symbol=symbol,
            decision_time=decision_time,
            feature_available_at=available_at,
            features=features,
            label=label,
            label_available_at=label_available_at,
            source_document_ids=tuple(d.document_id for d in eligible),
        )
        row.validate()
        return row
