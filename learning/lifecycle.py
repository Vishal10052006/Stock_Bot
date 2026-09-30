"""Learning lifecycle state and champion/rollback persistence.

The state machine is intentionally fail-closed. Model registry approval remains
an explicit governance operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .self_learning_models import ChampionRecord


@dataclass(frozen=True, slots=True)
class RollbackRecord:
    """Immutable record of a rollback event."""

    rollback_id: str
    from_model_version: str
    to_model_version: str
    reason: str
    timestamp: str
    review_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "rollback_id",
            "from_model_version",
            "to_model_version",
            "reason",
            "timestamp",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.from_model_version == self.to_model_version:
            raise ValueError("rollback versions must differ")
        if len(self.review_fingerprint) != 64:
            raise ValueError("review_fingerprint must be SHA-256")

    @property
    def fingerprint(self) -> str:
        """Return deterministic rollback identity."""
        payload = {
            "rollback_id": self.rollback_id,
            "from_model_version": self.from_model_version,
            "to_model_version": self.to_model_version,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "review_fingerprint": self.review_fingerprint,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()


class ChampionStore:
    """Append-only champion history with a current-version pointer."""

    def __init__(self, history_path: str | Path) -> None:
        self.history_path = Path(history_path)
        self.pointer_path = self.history_path.with_suffix(".current")

    def activate(self, record: ChampionRecord) -> None:
        """Persist one approved champion activation."""
        if not isinstance(record, ChampionRecord):
            raise TypeError("record must be a ChampionRecord")
        if record.status != "PROMOTED":
            raise ValueError("only PROMOTED records can be activated")

        prior = self.history()
        if prior and record.parent_model_version != prior[-1].model_version:
            raise ValueError("champion parent must match current champion")

        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_version": record.model_version,
            "status": record.status,
            "activated_at": record.activated_at,
            "experiment_id": record.experiment_id,
            "promotion_review_fingerprint": record.promotion_review_fingerprint,
            "parent_model_version": record.parent_model_version,
            "rollback_of": record.rollback_of,
            "fingerprint": record.fingerprint,
        }
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")

        self.pointer_path.write_text(record.model_version, encoding="utf-8")

    def current(self) -> str | None:
        """Return the current champion model version."""
        if not self.pointer_path.exists():
            return None
        value = self.pointer_path.read_text(encoding="utf-8").strip()
        return value or None

    def history(self) -> tuple[ChampionRecord, ...]:
        """Load and verify champion history."""
        if not self.history_path.exists():
            return ()

        result: list[ChampionRecord] = []
        for line_number, line in enumerate(
            self.history_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise ValueError(f"blank champion history line {line_number}")
            payload = json.loads(line)
            expected = payload.pop("fingerprint", None)
            record = ChampionRecord(**payload)
            if expected is not None and expected != record.fingerprint:
                raise ValueError(
                    f"champion history fingerprint mismatch at line {line_number}"
                )
            result.append(record)

        return tuple(result)


class LearningLifecycle:
    """Explicit state transition graph for one self-learning cycle."""

    _TRANSITIONS = {
        "OBSERVATION": {"HYPOTHESIS", "INCONCLUSIVE"},
        "HYPOTHESIS": {"EXPERIMENT", "INCONCLUSIVE"},
        "EXPERIMENT": {"CANDIDATE", "REJECTED", "INCONCLUSIVE"},
        "CANDIDATE": {"VALIDATING", "REJECTED", "INCONCLUSIVE"},
        "VALIDATING": {"OOS", "REJECTED", "INCONCLUSIVE"},
        "OOS": {"WALK_FORWARD", "REJECTED", "INCONCLUSIVE"},
        "WALK_FORWARD": {"PAPER", "REJECTED", "INCONCLUSIVE"},
        "PAPER": {"PROMOTION_REVIEW", "REJECTED", "INCONCLUSIVE"},
        "PROMOTION_REVIEW": {"PROMOTED", "REJECTED", "INCONCLUSIVE"},
        "PROMOTED": {"ROLLED_BACK"},
        "ROLLED_BACK": set(),
        "REJECTED": set(),
        "INCONCLUSIVE": set(),
    }

    def can_transition(self, current: str, target: str) -> bool:
        """Return whether a state transition is allowed."""
        return target in self._TRANSITIONS.get(current, set())

    def require_transition(self, current: str, target: str) -> None:
        """Raise when a transition is not explicitly allowed."""
        if not self.can_transition(current, target):
            raise ValueError(
                f"illegal learning transition: {current} -> {target}"
            )
