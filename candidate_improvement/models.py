"""Phase-19 candidate improvement contracts.

Candidate improvements are immutable research proposals. They can describe a
strategy-side change, bind that change to learning evidence and a frozen
experiment definition, and nothing more. They cannot mutate strategy/risk
configuration or authorize execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.runner import ExperimentExecution


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class CandidateChangeField(str, Enum):
    MINIMUM_RVOL = "baseline.minimum_rvol"
    MINIMUM_REGIME_PROBABILITY = "baseline.minimum_regime_probability"
    PREDICTION_MIN_PROBABILITY = "prediction_min_probability"
    PREDICTION_MIN_MARGIN = "prediction_min_margin"
    PREDICTION_MAX_AGE_SECONDS = "prediction_max_age_seconds"
    EXPECTED_VALUE_THRESHOLD = "expected_value_threshold"
    MAX_COST_FRACTION = "max_cost_fraction"
    ALLOWED_REGIMES = "allowed_regimes"
    REQUIRE_PREDICTION_DIRECTION_ALIGNMENT = "require_prediction_direction_alignment"
    REQUIRE_ANALYSIS_ALIGNMENT = "require_analysis_alignment"
    REQUIRE_LIQUIDITY_WHEN_PRESENT = "require_liquidity_when_present"


ALLOWED_CHANGE_FIELDS = frozenset(item.value for item in CandidateChangeField)


@dataclass(frozen=True, slots=True)
class CandidateImprovementProposal:
    """One auditable, non-deployable strategy-change proposal."""

    candidate_id: str
    status: CandidateStatus
    hypothesis: str
    rationale: str
    source_learning_fingerprint: str
    source_trade_ids: tuple[str, ...]
    baseline_strategy_fingerprint: str
    parameter_changes: tuple[tuple[str, str], ...]
    experiment_definition_fingerprint: str
    evidence_confidence: float
    evidence_count: int

    def __post_init__(self) -> None:
        for name in (
            "candidate_id",
            "hypothesis",
            "rationale",
            "source_learning_fingerprint",
            "baseline_strategy_fingerprint",
            "experiment_definition_fingerprint",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if not self.source_trade_ids:
            raise ValueError("source_trade_ids must not be empty")
        if len(self.source_trade_ids) != len(set(self.source_trade_ids)):
            raise ValueError("source_trade_ids must be unique")
        keys = tuple(key for key, _ in self.parameter_changes)
        if len(keys) != len(set(keys)):
            raise ValueError("parameter_changes keys must be unique")
        if any(key not in ALLOWED_CHANGE_FIELDS for key in keys):
            raise ValueError("parameter_changes contains a forbidden field")
        if self.evidence_count < 1:
            raise ValueError("evidence_count must be positive")
        if not 0.0 <= self.evidence_confidence <= 1.0:
            raise ValueError("evidence_confidence must be in [0, 1]")

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "hypothesis": self.hypothesis,
            "rationale": self.rationale,
            "source_learning_fingerprint": self.source_learning_fingerprint,
            "source_trade_ids": list(self.source_trade_ids),
            "baseline_strategy_fingerprint": self.baseline_strategy_fingerprint,
            "parameter_changes": {k: v for k, v in self.parameter_changes},
            "experiment_definition_fingerprint": self.experiment_definition_fingerprint,
            "evidence_confidence": self.evidence_confidence,
            "evidence_count": self.evidence_count,
        }

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateValidation:
    """Validation result; validation does not promote or deploy a candidate."""

    accepted: bool
    candidate_fingerprint: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateExperimentBinding:
    """Immutable proof that a candidate is bound to one frozen experiment."""

    candidate_fingerprint: str
    experiment_definition_fingerprint: str
    parameter_changes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.candidate_fingerprint.strip():
            raise ValueError("candidate_fingerprint must be non-empty")
        if not self.experiment_definition_fingerprint.strip():
            raise ValueError("experiment_definition_fingerprint must be non-empty")
        if not self.parameter_changes:
            raise ValueError("parameter_changes must not be empty")

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "candidate_fingerprint": self.candidate_fingerprint,
                "experiment_definition_fingerprint": self.experiment_definition_fingerprint,
                "parameter_changes": list(self.parameter_changes),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateExperimentExecution:
    """Immutable candidate binding paired with the existing experiment result."""

    binding: CandidateExperimentBinding
    execution: "ExperimentExecution"

    def __post_init__(self) -> None:
        if not isinstance(self.execution, object):
            raise TypeError("execution must be an ExperimentExecution")

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "binding": self.binding.fingerprint,
                "execution_record": self.execution.record.fingerprint,
                "experiment_definition": self.execution.definition.fingerprint(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
