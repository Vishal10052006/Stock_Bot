"""Explicit failure classification for Analysis Bot."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class AnalysisFailureType(str, Enum):
    DATA_FAILURE = "DATA_FAILURE"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    TIMESTAMP_FAILURE = "TIMESTAMP_FAILURE"
    CALCULATION_FAILURE = "CALCULATION_FAILURE"
    SCHEMA_FAILURE = "SCHEMA_FAILURE"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    ARCHITECTURE_FAILURE = "ARCHITECTURE_FAILURE"


@dataclass(frozen=True, slots=True)
class AnalysisFailure:
    """Structured failure record; never silently converted into context."""
    failure_type: AnalysisFailureType
    message: str
    component: str
    recoverable: bool = False
