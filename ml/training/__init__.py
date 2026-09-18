"""
Phase 9 ML training public API.
"""

from .models import (
    TrainingConfig,
    TrainingResult,
)
from .trainer import train_baseline

__all__ = [
    "TrainingConfig",
    "TrainingResult",
    "train_baseline",
]
