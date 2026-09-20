"""AB-25 AnalysisContext -> Phase 9 prediction adapter.

The adapter reuses the existing Phase 9 FeaturePreprocessor, LogisticOutcomeModel,
and IsotonicProbabilityCalibrator. It is intentionally inference-only: no labels,
future data, training, strategy, risk, or execution logic are introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from intelligence.analysis.contracts import AnalysisContext
from ml.models.logistic import LogisticOutcomeModel, MODEL_CLASSES
from ml.preprocessing.pipeline import FeaturePreprocessor


@dataclass(frozen=True, slots=True)
class PredictionContext:
    """Auditable prediction output for one AnalysisContext."""

    timestamp: pd.Timestamp
    symbol: str
    probabilities: pd.DataFrame
    predicted_class: str
    model_version: str
    feature_version: str
    analysis_version: str

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("prediction timestamp must be timezone-aware")
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.predicted_class not in MODEL_CLASSES:
            raise ValueError("predicted_class must be a canonical Phase 9 class")
        if list(self.probabilities.columns) != list(MODEL_CLASSES):
            raise ValueError("probabilities must use the canonical Phase 9 class order")
        if len(self.probabilities) != 1:
            raise ValueError("PredictionContext requires exactly one probability row")
        if not self.probabilities.apply(
            lambda column: column.between(0.0, 1.0).all()
        ).all():
            raise ValueError("prediction probabilities must lie in [0, 1]")
        if not self.probabilities.sum(axis=1).sub(1.0).abs().le(1e-8).all():
            raise ValueError("prediction probabilities must sum to 1")


def predict_from_analysis(
    context: AnalysisContext,
    *,
    model: LogisticOutcomeModel,
    preprocessor: FeaturePreprocessor,
    model_version: str = "phase9-logistic-v1",
) -> PredictionContext:
    """Generate Phase 9 probabilities from one validated AnalysisContext."""
    if not isinstance(context, AnalysisContext):
        raise TypeError("context must be an AnalysisContext")
    if not isinstance(model, LogisticOutcomeModel):
        raise TypeError("model must be a LogisticOutcomeModel")
    if not model.is_fitted:
        raise ValueError("model must be fitted before inference")
    if not isinstance(preprocessor, FeaturePreprocessor):
        raise TypeError("preprocessor must be a FeaturePreprocessor")
    if not preprocessor.is_fitted:
        raise ValueError("preprocessor must be fitted before inference")
    if model.feature_count != len(preprocessor.get_feature_names_out()):
        raise ValueError("model/preprocessor feature counts do not match")

    row = pd.DataFrame([dict(context.feature_vector)])

    # Use the same Phase 9 feature schema and train-fitted preprocessing.
    transformed = preprocessor.transform(row)
    probabilities = model.predict_proba(transformed)
    predicted_class = str(probabilities.iloc[0].idxmax())

    return PredictionContext(
        timestamp=context.timestamp,
        symbol=context.symbol,
        probabilities=probabilities,
        predicted_class=predicted_class,
        model_version=model_version,
        feature_version=context.feature_version,
        analysis_version=context.analysis_version,
    )
