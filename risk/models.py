"""
Stock Bot — Risk Data Models

Defines the normalized risk decision contract used by
the risk engine and execution gate.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Literal


RiskDecision = Literal["APPROVE", "REJECT"]


@dataclass(frozen=True)
class RiskResult:
    """Represents the result of a risk evaluation."""

    decision: RiskDecision
    risk_score: float
    reason: str

    def __post_init__(self):
        """Validate the risk contract."""

        if self.decision not in ("APPROVE", "REJECT"):
            raise ValueError("decision must be APPROVE or REJECT")

        # Reject NaN and infinite risk scores before range validation.
        if not isfinite(float(self.risk_score)):
            raise ValueError("risk_score must be finite")

        if not 0.0 <= self.risk_score <= 1.0:
            raise ValueError("risk_score must be between 0.0 and 1.0")

        if not self.reason:
            raise ValueError("reason must not be empty")
