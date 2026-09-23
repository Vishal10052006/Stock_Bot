"""Phase-19 evidence-to-candidate proposal engine."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

from experiments.definition import ExperimentDefinition
from learning.models import LearningExperience

from .models import (
    ALLOWED_CHANGE_FIELDS,
    CandidateChangeField,
    CandidateImprovementProposal,
    CandidateStatus,
    CandidateValidation,
)


class CandidateImprovementEngine:
    """Convert learning evidence into bounded research candidates.

    The engine only proposes changes to the StrategyConfig surface explicitly
    whitelisted by CandidateChangeField. It never mutates the supplied
    configuration and never promotes or enables execution.
    """

    def propose(
        self,
        experience: LearningExperience,
        *,
        baseline_strategy_fingerprint: str,
        parameter_changes: Mapping[str, object],
        experiment_definition: ExperimentDefinition,
        candidate_id: str,
    ) -> CandidateImprovementProposal:
        if not isinstance(experience, LearningExperience):
            raise TypeError("experience must be a LearningExperience")
        if not isinstance(experiment_definition, ExperimentDefinition):
            raise TypeError("experiment_definition must be an ExperimentDefinition")
        if not baseline_strategy_fingerprint.strip():
            raise ValueError("baseline_strategy_fingerprint must be non-empty")
        if not candidate_id.strip():
            raise ValueError("candidate_id must be non-empty")
        if not parameter_changes:
            raise ValueError("parameter_changes must not be empty")

        normalized = []
        for key, value in sorted(parameter_changes.items()):
            if key not in ALLOWED_CHANGE_FIELDS:
                raise ValueError(f"forbidden candidate change field: {key}")
            normalized.append((key, self._serialize_value(value)))

        allowed_by_experiment = set(experiment_definition.allowed_change)
        if not allowed_by_experiment:
            raise ValueError("experiment definition must declare allowed_change")
        undeclared = set(parameter_changes) - allowed_by_experiment
        if undeclared:
            raise ValueError(
                "candidate changes are not declared by experiment: "
                + ", ".join(sorted(undeclared))
            )

        expected_experiment = experiment_definition.fingerprint()
        learning_fingerprint = self._learning_fingerprint(experience)

        hypothesis = (
            f"Test whether changing {', '.join(key for key, _ in normalized)} "
            f"reduces the observed {experience.pattern.value} condition without "
            "degrading the frozen baseline under the defined experiment."
        )

        return CandidateImprovementProposal(
            candidate_id=candidate_id.strip(),
            status=CandidateStatus.PROPOSED,
            hypothesis=hypothesis,
            rationale=experience.rationale,
            source_learning_fingerprint=learning_fingerprint,
            source_trade_ids=experience.source_trade_ids,
            baseline_strategy_fingerprint=baseline_strategy_fingerprint.strip(),
            parameter_changes=tuple(normalized),
            experiment_definition_fingerprint=expected_experiment,
            evidence_confidence=experience.confidence,
            evidence_count=experience.evidence_count,
        )

    @staticmethod
    def validate(
        candidate: CandidateImprovementProposal,
        *,
        minimum_evidence: int = 3,
        minimum_confidence: float = 0.0,
    ) -> CandidateValidation:
        if not isinstance(candidate, CandidateImprovementProposal):
            raise TypeError("candidate must be a CandidateImprovementProposal")
        reasons: list[str] = []
        if candidate.status is not CandidateStatus.PROPOSED:
            reasons.append("candidate must be PROPOSED")
        if candidate.evidence_count < minimum_evidence:
            reasons.append("insufficient evidence")
        if candidate.evidence_confidence < minimum_confidence:
            reasons.append("insufficient evidence confidence")
        for key, _ in candidate.parameter_changes:
            if key not in ALLOWED_CHANGE_FIELDS:
                reasons.append(f"forbidden candidate change field: {key}")
        return CandidateValidation(
            accepted=not reasons,
            candidate_fingerprint=candidate.fingerprint,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _serialize_value(value: object) -> str:
        try:
            return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate parameter value must be serializable") from exc

    @staticmethod
    def _learning_fingerprint(experience: LearningExperience) -> str:
        payload = {
            "pattern": experience.pattern.value,
            "error_class": experience.error_class.value,
            "source_trade_ids": list(experience.source_trade_ids),
            "conditions": list(experience.conditions),
            "evidence_count": experience.evidence_count,
            "population_count": experience.population_count,
            "occurrence_rate": experience.occurrence_rate,
            "confidence": experience.confidence,
            "average_net_pnl": experience.average_net_pnl,
            "total_net_pnl": experience.total_net_pnl,
            "rationale": experience.rationale,
            "detail": experience.detail,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


__all__ = ["CandidateImprovementEngine"]
