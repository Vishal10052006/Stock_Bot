"""
Phase 9 TrainingDataset public API.
"""

from .builder import build_training_dataset
from .models import TrainingDataset
from .splitting import (
    TemporalSplit,
    TemporalSplitConfig,
    temporal_split,
)
from .validation import (
    EXPECTED_COLUMNS,
    VALID_LABELS,
    validate_training_dataset,
)
from .pipeline import (
    Phase9DatasetResult,
    build_phase9_dataset,
)

__all__ = [
    "EXPECTED_COLUMNS",
    "VALID_LABELS",
    "TrainingDataset",
    "TemporalSplit",
    "TemporalSplitConfig",
    "build_training_dataset",
    "temporal_split",
    "validate_training_dataset",
    "Phase9DatasetResult",
    "build_phase9_dataset",
    "MultiSymbolPhase9Failure",
    "MultiSymbolPhase9InstrumentResult",
    "MultiSymbolPhase9Result",
    "build_multi_symbol_phase9_dataset",
]

from .multi_symbol import (
    MultiSymbolPhase9Failure,
    MultiSymbolPhase9InstrumentResult,
    MultiSymbolPhase9Result,
    build_multi_symbol_phase9_dataset,
)
