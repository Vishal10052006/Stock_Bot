"""Versioned Strategy Engine registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .models import StrategyConfig


@dataclass(frozen=True, slots=True)
class StrategyRegistration:
    """Immutable strategy registration metadata."""

    config: StrategyConfig
    status: str = "RESEARCH"
    validation_reference: str | None = None


class StrategyRegistry:
    """Deterministic in-memory registry for reproducible research."""

    def __init__(
        self,
        registrations: Mapping[str, StrategyRegistration] | None = None,
    ) -> None:
        self._registrations = dict(registrations or {})

    def register(self, registration: StrategyRegistration) -> None:
        """Register one strategy version without silently replacing it."""
        version = registration.config.strategy_version

        if version in self._registrations:
            raise ValueError(
                f"strategy version already registered: {version}"
            )

        self._registrations[version] = registration

    def get(self, version: str) -> StrategyRegistration:
        """Return an exact registered strategy version."""
        try:
            return self._registrations[version]
        except KeyError as exc:
            raise KeyError(
                f"unknown strategy version: {version}"
            ) from exc

    def versions(self) -> tuple[str, ...]:
        """Return registered versions in deterministic order."""
        return tuple(sorted(self._registrations))
