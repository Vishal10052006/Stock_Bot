"""Immutable, serializable record for one completed experiment run."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from .definition import ExperimentDefinition


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    """Measured result envelope tied to one frozen experiment definition."""

    definition_fingerprint: str
    observations: int
    label_distribution: tuple[tuple[str, int], ...]
    baseline_results: dict[str, Any]
    model_results: dict[str, Any]
    stratified_results: dict[str, Any]
    effective_sample_size_notes: str
    limitations: tuple[str, ...]
    interpretation: str
    decision: str
    root_cause: str
    lesson: str
    next_experiment: str

    def __post_init__(self) -> None:
        """Validate the experiment record without evaluating its merits."""
        if not self.definition_fingerprint:
            raise ValueError("definition_fingerprint must not be empty")
        if self.observations < 0:
            raise ValueError("observations must not be negative")
        if self.decision not in {"KEEP", "REJECT", "INCONCLUSIVE"}:
            raise ValueError(
                "decision must be KEEP, REJECT, or INCONCLUSIVE"
            )

    @classmethod
    def from_definition(
        cls,
        definition: ExperimentDefinition,
        *,
        observations: int,
        label_distribution: dict[str, int] | None = None,
        baseline_results: dict[str, Any] | None = None,
        model_results: dict[str, Any] | None = None,
        stratified_results: dict[str, Any] | None = None,
        effective_sample_size_notes: str = "",
        limitations: tuple[str, ...] = (),
        interpretation: str = "",
        decision: str = "INCONCLUSIVE",
        root_cause: str = "",
        lesson: str = "",
        next_experiment: str = "",
    ) -> "ExperimentRecord":
        """Bind measured fields to an immutable definition fingerprint."""
        if not isinstance(definition, ExperimentDefinition):
            raise TypeError("definition must be an ExperimentDefinition")

        distribution = tuple(
            sorted(
                (str(label), int(count))
                for label, count in (label_distribution or {}).items()
            )
        )

        return cls(
            definition_fingerprint=definition.fingerprint(),
            observations=observations,
            label_distribution=distribution,
            baseline_results=baseline_results or {},
            model_results=model_results or {},
            stratified_results=stratified_results or {},
            effective_sample_size_notes=effective_sample_size_notes,
            limitations=tuple(limitations),
            interpretation=interpretation,
            decision=decision,
            root_cause=root_cause,
            lesson=lesson,
            next_experiment=next_experiment,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible record data."""
        result = asdict(self)
        result["label_distribution"] = {
            label: count
            for label, count in self.label_distribution
        }
        result["limitations"] = list(self.limitations)
        return result

    def canonical_json(self) -> str:
        """Serialize the record deterministically."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def fingerprint(self) -> str:
        """Return a stable identity for the complete measured record."""
        return hashlib.sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()
