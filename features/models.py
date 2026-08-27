"""
Stock Bot — Feature Data Models

Defines normalized feature values produced from market data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSet:
    """Represents calculated market features for one symbol."""

    symbol: str
    timestamp: object
    values: dict[str, float]

    def __post_init__(self):
        """Validate the feature contract."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if not self.values:
            raise ValueError("values must not be empty")

        for name, value in self.values.items():
            if not name:
                raise ValueError("feature name must not be empty")

            if not isinstance(value, (int, float)):
                raise ValueError("feature values must be numeric")
