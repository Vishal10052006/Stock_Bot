"""Champion state and rollback journal.

This is a research/governance deployment pointer.  It never calls Strategy,
Risk, Execution, broker, or live-trading code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ChampionState:
    """Immutable pointer to the currently approved model version."""

    champion_version: str
    previous_verified_version: str | None
    promotion_fingerprint: str | None = None
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.champion_version.strip():
            raise ValueError("champion_version must not be empty")
        if self.previous_verified_version == self.champion_version:
            raise ValueError("previous_verified_version must differ from champion")


class ChampionStateStore:
    """Append-only champion/rollback state file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, state: ChampionState) -> None:
        """Persist an immutable champion-state transition."""
        existing = self.current
        if existing is not None:
            if (
                existing.champion_version == state.champion_version
                and existing.previous_verified_version == state.previous_verified_version
                and existing.promotion_fingerprint == state.promotion_fingerprint
                and existing.updated_at == state.updated_at
            ):
                raise ValueError("identical champion state already recorded")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "champion_version": state.champion_version,
            "previous_verified_version": state.previous_verified_version,
            "promotion_fingerprint": state.promotion_fingerprint,
            "updated_at": state.updated_at,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")

    @property
    def current(self) -> ChampionState | None:
        """Return the most recent validated state."""
        if not self.path.exists():
            return None

        current: ChampionState | None = None
        for line_no, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise ValueError(f"blank champion state line {line_no}")
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"invalid champion state line {line_no}")
            current = ChampionState(
                champion_version=str(payload["champion_version"]),
                previous_verified_version=(
                    None
                    if payload.get("previous_verified_version") is None
                    else str(payload["previous_verified_version"])
                ),
                promotion_fingerprint=(
                    None
                    if payload.get("promotion_fingerprint") is None
                    else str(payload["promotion_fingerprint"])
                ),
                updated_at=str(payload.get("updated_at", "")),
            )
        return current

    def rollback(self, *, reason: str, updated_at: str) -> ChampionState:
        """Move the pointer back to the previously verified version."""
        current = self.current
        if current is None:
            raise ValueError("cannot rollback without a champion state")
        if not current.previous_verified_version:
            raise ValueError("no previous verified version is available")
        if not reason.strip():
            raise ValueError("rollback reason is required")

        next_state = ChampionState(
            champion_version=current.previous_verified_version,
            previous_verified_version=current.champion_version,
            promotion_fingerprint=current.promotion_fingerprint,
            updated_at=updated_at,
        )
        self.append(next_state)
        return next_state


__all__ = ["ChampionState", "ChampionStateStore"]
