"""Immutable state-store services for the STOCK_BOT learning loop.

The stores are intentionally small and append-only. They provide persistence
for learning cycles, champion history, and rollback evidence without granting
trading or broker authority.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from .self_learning_models import LearningCycle


class LearningCycleStore:
    """Append-only JSONL persistence for end-to-end learning-cycle records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, cycle: LearningCycle) -> None:
        """Persist one immutable cycle, rejecting conflicting IDs."""
        if not isinstance(cycle, LearningCycle):
            raise TypeError("cycle must be a LearningCycle")

        for prior in self.read_all():
            if prior.cycle_id == cycle.cycle_id:
                if prior.fingerprint != cycle.fingerprint:
                    raise ValueError("cycle_id collision with different content")
                return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(cycle)
        payload["state"] = cycle.state.value
        payload["decision"] = cycle.decision.value
        payload["failure_class"] = (
            None if cycle.failure_class is None else cycle.failure_class.value
        )
        payload["fingerprint"] = cycle.fingerprint
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(payload, sort_keys=True, separators=(",", ":"))
                + "\n"
            )

    def read_all(self) -> tuple[LearningCycle, ...]:
        """Load persisted cycles and verify deterministic identities."""
        if not self.path.exists():
            return ()

        result: list[LearningCycle] = []
        from .self_learning_models import FailureClass, LearningDecision, LearningState

        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise ValueError(f"blank learning-cycle line {line_number}")
            payload = json.loads(line)
            expected = payload.pop("fingerprint", None)
            cycle = LearningCycle(
                cycle_id=str(payload["cycle_id"]),
                state=LearningState(str(payload["state"])),
                experience_fingerprints=tuple(payload["experience_fingerprints"]),
                learning_evidence_fingerprints=tuple(
                    payload["learning_evidence_fingerprints"]
                ),
                experiment_id=payload.get("experiment_id"),
                candidate_id=payload.get("candidate_id"),
                promotion_review_fingerprint=payload.get(
                    "promotion_review_fingerprint"
                ),
                decision=LearningDecision(str(payload["decision"])),
                failure_class=(
                    None
                    if payload.get("failure_class") is None
                    else FailureClass(str(payload["failure_class"]))
                ),
                lesson=str(payload.get("lesson", "")),
                next_experiment=str(payload.get("next_experiment", "")),
            )
            if expected is not None and expected != cycle.fingerprint:
                raise ValueError(
                    f"learning-cycle fingerprint mismatch at line {line_number}"
                )
            result.append(cycle)

        return tuple(result)


def fingerprints(items: Iterable[object]) -> tuple[str, ...]:
    """Extract deterministic fingerprints from immutable learning objects."""
    values: list[str] = []
    for item in items:
        fingerprint = getattr(item, "fingerprint", None)
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise TypeError("items must expose a SHA-256 fingerprint")
        values.append(fingerprint)
    return tuple(values)
