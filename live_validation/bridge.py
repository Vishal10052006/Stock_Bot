"""Adapter from existing prediction inference to live-validation evidence.

The bridge keeps ML prediction inference and future-outcome evaluation
separate. It snapshots the exact decision-time row needed by Phase 7 before
the market can move further.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ml.prediction.contracts import ClassificationPrediction
from ml.labeling import LabelingConfig
from trading.signals.models import CandidateConfig

from .journal import LiveValidationJournal
from .models import LivePrediction
from .resolver import LiveOutcomeResolver


class LivePredictionValidationBridge:
    """Record predictions and resolve them as future live candles arrive."""

    def __init__(
        self,
        journal: LiveValidationJournal,
        *,
        labeling_config: LabelingConfig | None = None,
        candidate_config: CandidateConfig | None = None,
    ) -> None:
        self.journal = journal
        self.resolver = LiveOutcomeResolver(
            labeling_config=labeling_config,
            candidate_config=candidate_config,
        )

    def record_prediction(
        self,
        prediction: ClassificationPrediction,
        decision_row: pd.Series,
    ) -> LivePrediction:
        """Persist one live prediction with its causal candidate snapshot."""
        if not isinstance(prediction, ClassificationPrediction):
            raise TypeError("prediction must be a ClassificationPrediction")

        prediction_id = self.journal.prediction_id(
            timestamp=prediction.timestamp,
            symbol=prediction.symbol,
            model_version=prediction.provenance.model_version,
        )

        live_prediction = self.resolver.create_prediction(
            prediction_id=prediction_id,
            timestamp=prediction.timestamp,
            symbol=prediction.symbol,
            model_version=prediction.provenance.model_version,
            feature_version=prediction.provenance.feature_version,
            dataset_version=prediction.provenance.dataset_version,
            probabilities=dict(prediction.probabilities),
            generated_at=pd.Timestamp.now(tz="UTC"),
            decision_row=decision_row,
        )
        self.journal.append_prediction(live_prediction)
        return live_prediction

    def update_outcome(
        self,
        prediction: LivePrediction,
        candles: pd.DataFrame,
        *,
        resolved_at: datetime | pd.Timestamp | None = None,
    ):
        """Resolve a prediction once enough completed future candles exist."""
        outcome = self.resolver.resolve(
            prediction,
            candles,
            resolved_at=resolved_at or datetime.now(timezone.utc),
        )
        latest = self.journal.read_latest_outcomes().get(
            prediction.prediction_id
        )

        # Avoid appending duplicate RESOLVED records. PENDING observations may
        # be refreshed repeatedly as new live candles arrive.
        if (
            outcome.status.value == "RESOLVED"
            and latest is not None
            and latest.status.value == "RESOLVED"
        ):
            return latest

        self.journal.append_outcome(outcome)
        return outcome
