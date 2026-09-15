"""Research signal and trade-candidate construction."""

from .adapter import build_candidate_from_decision
from .candidate import build_candidate
from .models import (
    CandidateConfig,
    CandidateDirection,
    TradeCandidate,
)
from .validation import (
    validate_candidate,
    validate_candidates,
)

__all__ = [
    "CandidateConfig",
    "CandidateDirection",
    "TradeCandidate",
    "build_candidate",
    "build_candidate_from_decision",
    "validate_candidate",
    "validate_candidates",
]
