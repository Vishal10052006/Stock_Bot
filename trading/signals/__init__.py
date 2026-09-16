"""Research signal and trade-candidate construction."""

from .adapter import build_candidate_from_decision
from .candidate import build_candidate
from .directional import build_directional_candidates
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
    "build_directional_candidates",
    "build_candidate_from_decision",
    "validate_candidate",
    "validate_candidates",
]
