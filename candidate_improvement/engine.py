"""Phase-19 evidence-to-candidate proposal engine."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Callable, Mapping

from experiments.definition import ExperimentDefinition
from experiments.record import ExperimentRecord
from experiments.runner import ExperimentExecution, ExperimentRunner
from learning.models import LearningExperience
from trading.strategy.models import BaselineStrategyConfig, StrategyConfig

from .models import (
    ALLOWED_CHANGE_FIELDS,
    CandidateExperimentBinding,
    CandidateExperimentExecution,
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
        missing_from_candidate = allowed_by_experiment - set(parameter_changes)
        if missing_from_candidate:
            raise ValueError(
                "experiment declares changes not present in candidate: "
                + ", ".join(sorted(missing_from_candidate))
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
    def bind_to_experiment(
        candidate: CandidateImprovementProposal,
        experiment_definition: ExperimentDefinition,
    ) -> CandidateExperimentBinding:
        """Bind a candidate only to the exact frozen definition it declares."""
        if not isinstance(candidate, CandidateImprovementProposal):
            raise TypeError("candidate must be a CandidateImprovementProposal")
        if not isinstance(experiment_definition, ExperimentDefinition):
            raise TypeError("experiment_definition must be an ExperimentDefinition")
        if candidate.status is not CandidateStatus.PROPOSED:
            raise ValueError("candidate must remain PROPOSED before experiment binding")

        definition_fingerprint = experiment_definition.fingerprint()
        if candidate.experiment_definition_fingerprint != definition_fingerprint:
            raise ValueError("candidate experiment definition fingerprint mismatch")

        candidate_fields = {key for key, _ in candidate.parameter_changes}
        experiment_fields = set(experiment_definition.allowed_change)
        if candidate_fields != experiment_fields:
            raise ValueError("candidate parameter changes do not exactly match experiment allowed_change")

        return CandidateExperimentBinding(
            candidate_fingerprint=candidate.fingerprint,
            experiment_definition_fingerprint=definition_fingerprint,
            parameter_changes=candidate.parameter_changes,
        )

    @staticmethod
    def materialize_strategy_config(
        candidate: CandidateImprovementProposal,
        baseline_config: StrategyConfig,
        *,
        expected_baseline_fingerprint: str | None = None,
    ) -> StrategyConfig:
        """Create an immutable research-only StrategyConfig from a candidate.

        This is a pure constructor boundary. It never changes the supplied
        baseline object and never returns Risk/Execution configuration.
        """
        if not isinstance(candidate, CandidateImprovementProposal):
            raise TypeError("candidate must be a CandidateImprovementProposal")
        if not isinstance(baseline_config, StrategyConfig):
            raise TypeError("baseline_config must be a StrategyConfig")
        if candidate.status is not CandidateStatus.PROPOSED:
            raise ValueError("candidate must be PROPOSED before materialization")

        actual_fingerprint = CandidateImprovementEngine.strategy_config_fingerprint(
            baseline_config
        )
        if (
            expected_baseline_fingerprint is not None
            and actual_fingerprint != expected_baseline_fingerprint
        ):
            raise ValueError("baseline strategy fingerprint mismatch")
        if candidate.baseline_strategy_fingerprint != actual_fingerprint:
            raise ValueError("candidate is bound to a different baseline strategy")

        config = baseline_config
        for key, serialized_value in candidate.parameter_changes:
            value = json.loads(serialized_value)
            if key == "baseline.minimum_rvol":
                config = replace(
                    config,
                    baseline=replace(config.baseline, minimum_rvol=float(value)),
                )
            elif key == "baseline.minimum_regime_probability":
                config = replace(
                    config,
                    baseline=replace(
                        config.baseline,
                        minimum_regime_probability=float(value),
                    ),
                )
            elif key == "prediction_min_probability":
                config = replace(config, prediction_min_probability=float(value))
            elif key == "prediction_min_margin":
                config = replace(config, prediction_min_margin=float(value))
            elif key == "prediction_max_age_seconds":
                config = replace(config, prediction_max_age_seconds=int(value))
            elif key == "expected_value_threshold":
                config = replace(config, expected_value_threshold=float(value))
            elif key == "max_cost_fraction":
                config = replace(config, max_cost_fraction=float(value))
            elif key == "allowed_regimes":
                if not isinstance(value, (list, tuple)) or not value:
                    raise ValueError("allowed_regimes candidate value must be a non-empty sequence")
                config = replace(config, allowed_regimes=tuple(str(item) for item in value))
            elif key == "require_prediction_direction_alignment":
                config = replace(
                    config,
                    require_prediction_direction_alignment=bool(value),
                )
            elif key == "require_analysis_alignment":
                config = replace(config, require_analysis_alignment=bool(value))
            elif key == "require_liquidity_when_present":
                config = replace(config, require_liquidity_when_present=bool(value))
            else:
                raise ValueError(f"unsupported candidate change field: {key}")

        return config

    @staticmethod
    def strategy_config_fingerprint(config: StrategyConfig) -> str:
        """Return deterministic identity for a StrategyConfig research baseline."""
        if not isinstance(config, StrategyConfig):
            raise TypeError("config must be a StrategyConfig")
        payload = {
            "strategy_id": config.strategy_id,
            "strategy_version": config.strategy_version,
            "baseline": {
                "minimum_rvol": config.baseline.minimum_rvol,
                "minimum_regime_probability": config.baseline.minimum_regime_probability,
                "strategy_version": config.baseline.strategy_version,
            },
            "prediction_min_probability": config.prediction_min_probability,
            "prediction_min_margin": config.prediction_min_margin,
            "prediction_max_age_seconds": config.prediction_max_age_seconds,
            "expected_value_threshold": config.expected_value_threshold,
            "max_cost_fraction": config.max_cost_fraction,
            "allowed_regimes": list(config.allowed_regimes),
            "require_prediction_direction_alignment": config.require_prediction_direction_alignment,
            "require_analysis_alignment": config.require_analysis_alignment,
            "require_liquidity_when_present": config.require_liquidity_when_present,
            "cost_model_version": config.cost_model_version,
            "candidate_policy_version": config.candidate_policy_version,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @classmethod
    def execute_bound_experiment(
        cls,
        candidate: CandidateImprovementProposal,
        experiment_definition: ExperimentDefinition,
        executor: Callable[[ExperimentDefinition], ExperimentRecord],
    ) -> CandidateExperimentExecution:
        """Execute a bound candidate through the existing ExperimentRunner.

        The candidate is not applied by this method. The supplied executor owns
        experiment-specific research configuration and must return an immutable
        ExperimentRecord bound to the same definition.
        """
        binding = cls.bind_to_experiment(candidate, experiment_definition)
        execution: ExperimentExecution = ExperimentRunner(experiment_definition).run(executor)
        return CandidateExperimentExecution(binding=binding, execution=execution)

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
