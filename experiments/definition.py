"""Immutable experiment definition and reproducibility identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class ExperimentDefinition:
    """Frozen specification for one research/backtest experiment.

    The definition contains methodology and configuration, but no measured
    result.  A deterministic fingerprint lets result artifacts prove which
    experiment specification produced them.
    """

    experiment_id: str
    research_question: str
    hypothesis: str
    failure_criterion: str
    dataset_version: str
    code_version: str
    period_start: str
    period_end: str
    symbols: tuple[str, ...]
    method: str
    fixed_parameters: tuple[tuple[str, str], ...] = ()
    allowed_change: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject incomplete definitions before they can be executed."""
        required = (
            "experiment_id",
            "research_question",
            "hypothesis",
            "failure_criterion",
            "dataset_version",
            "code_version",
            "period_start",
            "period_end",
            "method",
        )

        for field_name in required:
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{field_name} must be a non-empty string"
                )

        if not self.symbols:
            raise ValueError("symbols must contain at least one symbol")

        if any(
            not isinstance(symbol, str) or not symbol.strip()
            for symbol in self.symbols
        ):
            raise ValueError("symbols must contain non-empty strings")

        keys = [key for key, _ in self.fixed_parameters]
        if len(keys) != len(set(keys)):
            raise ValueError("fixed_parameters keys must be unique")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible experiment definition."""
        result = asdict(self)
        result["symbols"] = list(self.symbols)
        result["fixed_parameters"] = {
            key: value
            for key, value in self.fixed_parameters
        }
        result["allowed_change"] = list(self.allowed_change)
        return result

    def canonical_json(self) -> str:
        """Serialize the definition deterministically for artifact identity."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )

    def fingerprint(self) -> str:
        """Return a stable SHA-256 fingerprint of the definition."""
        return hashlib.sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()
