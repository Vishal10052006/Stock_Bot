"""Phase 5 feature-engineering public API."""

from market.features.builder import (
    FEATURE_COLUMNS,
    FEATURE_VERSION,
    IDENTIFIER_COLUMNS,
    FeatureBuilder,
    build_features,
)

from market.features.validation import (
    EXPECTED_COLUMNS,
    FeatureDatasetValidator,
    validate_feature_dataset,
)

__all__ = [
    "FEATURE_COLUMNS",
    "FEATURE_VERSION",
    "IDENTIFIER_COLUMNS",
    "EXPECTED_COLUMNS",
    "FeatureBuilder",
    "FeatureDatasetValidator",
    "build_features",
    "validate_feature_dataset",
]
