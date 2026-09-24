"""Versioned Strategy Engine registry with controlled promotion lifecycle.

The registry is the governance boundary for strategy configurations. Candidate
strategies may be registered and explicitly approved only with evidence tied to
the exact immutable configuration. Approval is never automatic and the
registry has no Risk, Safety, broker, or live-execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

from .models import StrategyConfig


STRATEGY_RESEARCH = "RESEARCH"
STRATEGY_CANDIDATE = "CANDIDATE"
STRATEGY_APPROVED = "APPROVED"
STRATEGY_RETIRED = "RETIRED"


@dataclass(frozen=True, slots=True)
class StrategyRegistration:
    """Immutable strategy registration and governance provenance."""

    config: StrategyConfig
    status: str = STRATEGY_RESEARCH
    validation_reference: str | None = None
    evaluation_fingerprint: str | None = None
    lineage_id: str | None = None
    approval_reference: str | None = None
    approval_evaluator: str | None = None
    approval_fingerprint: str | None = None
    retirement_reason: str | None = None

    @property
    def config_fingerprint(self) -> str:
        """Return deterministic identity for the exact strategy configuration."""
        payload = {
            "strategy_id": self.config.strategy_id,
            "strategy_version": self.config.strategy_version,
            "baseline": {
                "minimum_rvol": self.config.baseline.minimum_rvol,
                "minimum_regime_probability": self.config.baseline.minimum_regime_probability,
                "strategy_version": self.config.baseline.strategy_version,
            },
            "prediction_min_probability": self.config.prediction_min_probability,
            "prediction_min_margin": self.config.prediction_min_margin,
            "prediction_max_age_seconds": self.config.prediction_max_age_seconds,
            "expected_value_threshold": self.config.expected_value_threshold,
            "max_cost_fraction": self.config.max_cost_fraction,
            "allowed_regimes": list(self.config.allowed_regimes),
            "require_prediction_direction_alignment": (
                self.config.require_prediction_direction_alignment
            ),
            "require_analysis_alignment": self.config.require_analysis_alignment,
            "require_liquidity_when_present": self.config.require_liquidity_when_present,
            "cost_model_version": self.config.cost_model_version,
            "candidate_policy_version": self.config.candidate_policy_version,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


class StrategyRegistry:
    """Deterministic strategy registry with explicit governance transitions."""

    def __init__(
        self,
        registrations: Mapping[str, StrategyRegistration] | None = None,
    ) -> None:
        self._registrations: dict[str, StrategyRegistration] = {}
        for version, registration in (registrations or {}).items():
            if not isinstance(version, str) or not version.strip():
                raise ValueError("strategy registry keys must be non-empty strings")
            if not isinstance(registration, StrategyRegistration):
                raise TypeError("strategy registry values must be StrategyRegistration")
            if registration.config.strategy_version != version:
                raise ValueError("registry key must match strategy_version")
            if registration.status == STRATEGY_APPROVED:
                raise ValueError(
                    "approved strategies must enter the registry through approve()"
                )
            self._registrations[version] = registration

    def register(self, registration: StrategyRegistration) -> StrategyRegistration:
        """Register an immutable RESEARCH/CANDIDATE strategy version."""
        if not isinstance(registration, StrategyRegistration):
            raise TypeError("registration must be StrategyRegistration")
        if registration.status not in {STRATEGY_RESEARCH, STRATEGY_CANDIDATE}:
            raise ValueError("register() accepts only RESEARCH or CANDIDATE strategies")

        version = registration.config.strategy_version
        if version in self._registrations:
            existing = self._registrations[version]
            if existing.config_fingerprint == registration.config_fingerprint:
                return existing
            raise ValueError(f"strategy version already registered: {version}")

        self._registrations[version] = registration
        return registration

    def get(self, version: str) -> StrategyRegistration:
        """Return an exact registered strategy version."""
        try:
            return self._registrations[version]
        except KeyError as exc:
            raise KeyError(f"unknown strategy version: {version}") from exc

    def approve(
        self,
        version: str,
        *,
        validation_reference: str,
        evaluation_fingerprint: str,
        lineage_id: str,
        approval_reference: str,
        evaluator: str,
    ) -> StrategyRegistration:
        """Explicitly approve one candidate after external governance evidence."""
        registration = self.get(version)
        if registration.status == STRATEGY_RETIRED:
            raise ValueError("retired strategy cannot be approved")
        if registration.status != STRATEGY_CANDIDATE:
            raise ValueError("only CANDIDATE strategies can be approved")

        fields = {
            "validation_reference": validation_reference,
            "evaluation_fingerprint": evaluation_fingerprint,
            "lineage_id": lineage_id,
            "approval_reference": approval_reference,
            "evaluator": evaluator,
        }
        if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
            raise ValueError("approval provenance fields must be non-empty")

        approval_payload = {
            "config_fingerprint": registration.config_fingerprint,
            "validation_reference": validation_reference,
            "evaluation_fingerprint": evaluation_fingerprint,
            "lineage_id": lineage_id,
            "approval_reference": approval_reference,
            "evaluator": evaluator,
        }
        approval_fingerprint = hashlib.sha256(
            json.dumps(
                approval_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

        approved = StrategyRegistration(
            config=registration.config,
            status=STRATEGY_APPROVED,
            validation_reference=validation_reference,
            evaluation_fingerprint=evaluation_fingerprint,
            lineage_id=lineage_id,
            approval_reference=approval_reference,
            approval_evaluator=evaluator,
            approval_fingerprint=approval_fingerprint,
        )
        self._registrations[version] = approved
        return approved

    def retire(self, version: str, *, reason: str) -> StrategyRegistration:
        """Retire a strategy while preserving all historical provenance."""
        registration = self.get(version)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("retirement reason must be non-empty")
        if registration.status == STRATEGY_RETIRED:
            raise ValueError("strategy is already retired")

        retired = StrategyRegistration(
            config=registration.config,
            status=STRATEGY_RETIRED,
            validation_reference=registration.validation_reference,
            evaluation_fingerprint=registration.evaluation_fingerprint,
            lineage_id=registration.lineage_id,
            approval_reference=registration.approval_reference,
            approval_evaluator=registration.approval_evaluator,
            approval_fingerprint=registration.approval_fingerprint,
            retirement_reason=reason.strip(),
        )
        self._registrations[version] = retired
        return retired

    def approved(self) -> tuple[StrategyRegistration, ...]:
        """Return approved strategies in deterministic version order."""
        return tuple(
            self._registrations[version]
            for version in sorted(self._registrations)
            if self._registrations[version].status == STRATEGY_APPROVED
        )

    def active_approved(self) -> StrategyRegistration:
        """Require exactly one active approved strategy for controlled use."""
        active = self.approved()
        if not active:
            raise LookupError("no approved strategy is registered")
        if len(active) > 1:
            raise ValueError("multiple approved strategies require explicit selection")
        return active[0]

    def versions(self) -> tuple[str, ...]:
        """Return registered versions in deterministic order."""
        return tuple(sorted(self._registrations))
