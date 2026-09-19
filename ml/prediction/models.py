"""Phase 9 SignalModel v1.0 prediction contract.

The SignalModel is the boundary between trained ML components and the
future Phase 10 decision engine. It returns probabilities only.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 9 deliverable: SignalModel v1.0.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from market.features.builder import FEATURE_COLUMNS


@dataclass(frozen=True)
class SignalPrediction:
    """One probability prediction at a decision timestamp."""

    timestamp: pd.Timestamp
    symbol: str
    long_probability: float
    short_probability: float
    no_edge_probability: float
    model_version: str = "1.0"


@dataclass
class SignalModel:
    """Production-shaped Phase 9 probability prediction wrapper."""

    preprocessor: object
    model: object
    calibrator: object
    version: str = "1.0"

    @classmethod
    def from_training_result(cls, training_result: object) -> "SignalModel":
        """Construct a SignalModel from a completed Phase 9 training result."""
        required = ("preprocessor", "model", "calibrator")
        missing = [name for name in required if not hasattr(training_result, name)]
        if missing:
            raise TypeError(
                "training_result is missing required components: "
                f"{missing}"
            )

        return cls(
            preprocessor=training_result.preprocessor,
            model=training_result.model,
            calibrator=training_result.calibrator,
        )

    def predict(
        self,
        features: pd.DataFrame,
        *,
        identifiers: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Return calibrated probabilities without making a trade decision."""
        if not getattr(self.preprocessor, "is_fitted", False):
            raise ValueError("SignalModel preprocessor must be fitted.")
        if not getattr(self.model, "is_fitted", False):
            raise ValueError("SignalModel model must be fitted.")
        if not getattr(self.calibrator, "is_fitted", False):
            raise ValueError("SignalModel calibrator must be fitted.")

        if not isinstance(features, pd.DataFrame):
            raise TypeError("features must be a pandas DataFrame.")

        expected = list(FEATURE_COLUMNS)
        if list(features.columns) != expected:
            raise ValueError(
                "features must contain the frozen Phase 5 FEATURE_COLUMNS "
                "in canonical order."
            )

        transformed = self.preprocessor.transform(features)
        raw_probabilities = self.model.predict_proba(transformed)
        probabilities = self.calibrator.transform(raw_probabilities)

        if identifiers is None:
            identifiers = pd.DataFrame(
                {
                    "timestamp": [pd.NaT] * len(features),
                    "symbol": ["UNKNOWN"] * len(features),
                }
            )
        else:
            self._validate_identifiers(identifiers, len(features))

        result = identifiers.reset_index(drop=True).copy()
        result["long_probability"] = probabilities["LONG_SUCCESS"].to_numpy()
        result["short_probability"] = probabilities["SHORT_SUCCESS"].to_numpy()
        result["no_edge_probability"] = probabilities["NO_EDGE"].to_numpy()
        result["model_version"] = self.version

        return result[
            [
                "timestamp",
                "symbol",
                "long_probability",
                "short_probability",
                "no_edge_probability",
                "model_version",
            ]
        ]

    @staticmethod
    def _validate_identifiers(
        identifiers: pd.DataFrame,
        expected_rows: int,
    ) -> None:
        """Validate optional prediction identifiers."""
        if not isinstance(identifiers, pd.DataFrame):
            raise TypeError("identifiers must be a pandas DataFrame.")

        required = {"timestamp", "symbol"}
        if not required.issubset(identifiers.columns):
            raise ValueError(
                "identifiers must contain timestamp and symbol columns."
            )

        if len(identifiers) != expected_rows:
            raise ValueError(
                "identifiers and features must contain the same number of rows."
            )
