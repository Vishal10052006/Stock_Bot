"""Orchestrate immutable validation evidence for one model candidate.

SL-25 coordinates existing validation contracts. It does not implement a new
backtest, OOS, walk-forward, or paper engine and it has no promotion or
execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .candidate_lifecycle import CandidateLifecycleController
from .contracts import CandidateLifecycle, ModelCandidate, ValidationSummary
from .validation import ValidationPolicy, validate_candidate


@dataclass(frozen=True, slots=True)
class ValidationRun:
    """Immutable evidence bundle for one candidate validation run."""

    candidate_fingerprint: str
    stages: tuple[ValidationSummary, ...]
    gate: ValidationSummary

    def __post_init__(self) -> None:
        if len(self.candidate_fingerprint) != 64:
            raise ValueError("candidate_fingerprint must be SHA-256")
        if not self.stages:
            raise ValueError("stages must not be empty")

    @property
    def stage_map(self) -> Mapping[str, ValidationSummary]:
        """Return stage evidence keyed by stage name."""
        return {summary.stage: summary for summary in self.stages}

    @property
    def fingerprint(self) -> str:
        """Return deterministic identity for the validation run."""
        from .contracts import _fingerprint

        return _fingerprint(self)


class ValidationOrchestrator:
    """Collect and gate validation evidence without creating trading authority."""

    def __init__(
        self,
        *,
        policy: ValidationPolicy | None = None,
        lifecycle: CandidateLifecycleController | None = None,
    ) -> None:
        self.policy = policy or ValidationPolicy()
        self.lifecycle = lifecycle or CandidateLifecycleController()

    def start(self, candidate: ModelCandidate, *, at: str) -> ModelCandidate:
        """Move a fresh candidate into the explicit VALIDATING state."""
        if not isinstance(candidate, ModelCandidate):
            raise TypeError("candidate must be a ModelCandidate")
        if candidate.lifecycle is not CandidateLifecycle.CANDIDATE:
            raise ValueError("only CANDIDATE models can start validation")
        return self.lifecycle.transition(
            candidate,
            CandidateLifecycle.VALIDATING,
            at=at,
        )

    def collect(
        self,
        candidate: ModelCandidate,
        validations: Mapping[str, ValidationSummary],
    ) -> ValidationRun:
        """Bind supplied stage evidence to a candidate and evaluate the gate."""
        if not isinstance(candidate, ModelCandidate):
            raise TypeError("candidate must be a ModelCandidate")
        if candidate.lifecycle is not CandidateLifecycle.VALIDATING:
            raise ValueError("candidate must be VALIDATING before evidence collection")
        if not isinstance(validations, Mapping):
            raise TypeError("validations must be a mapping")

        expected = set(self.policy.required_stages)
        supplied = set(validations)
        unknown = sorted(supplied - expected)
        if unknown:
            raise ValueError(f"unknown validation stages: {','.join(unknown)}")

        normalized: dict[str, ValidationSummary] = {}
        for stage in self.policy.required_stages:
            result = validations.get(stage)
            if result is not None:
                if not isinstance(result, ValidationSummary):
                    raise TypeError(f"validation stage {stage} must be a ValidationSummary")
                if result.stage != stage:
                    raise ValueError(
                        f"validation stage key {stage} does not match summary stage {result.stage}"
                    )
                normalized[stage] = result

        gate = validate_candidate(candidate, normalized, policy=self.policy)
        stages = tuple(normalized[stage] for stage in self.policy.required_stages if stage in normalized)
        return ValidationRun(
            candidate_fingerprint=candidate.fingerprint,
            stages=stages,
            gate=gate,
        )

    def complete(
        self,
        candidate: ModelCandidate,
        run: ValidationRun,
        *,
        at: str,
    ) -> ModelCandidate:
        """Advance a validating candidate only when all required evidence is valid."""
        if not isinstance(candidate, ModelCandidate):
            raise TypeError("candidate must be a ModelCandidate")
        if not isinstance(run, ValidationRun):
            raise TypeError("run must be a ValidationRun")
        if run.candidate_fingerprint != candidate.fingerprint:
            raise ValueError("validation run does not match candidate")
        if candidate.lifecycle is not CandidateLifecycle.VALIDATING:
            raise ValueError("candidate must be VALIDATING before completion")
        if not run.gate.valid:
            raise ValueError("validation gate is invalid")
        if not at.strip():
            raise ValueError("validation completion timestamp is required")

        candidate = self.lifecycle.transition(
            candidate,
            CandidateLifecycle.PAPER,
            at=at,
        )
        return self.lifecycle.transition(
            candidate,
            CandidateLifecycle.PROMOTION_REVIEW,
            at=at,
        )


__all__ = ["ValidationOrchestrator", "ValidationRun"]
