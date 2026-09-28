"""Deterministic M20 shadow-session manifest.

The manifest binds runtime safety, configured symbols, candle counts, and
session-journal evidence into one reproducible fingerprint. It is evidence
metadata only and cannot authorize execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class ShadowSessionManifest:
    """Immutable identity and evidence summary for one M20 session."""

    session_id: str
    mode: str
    live_broker_order_submission: bool
    symbols: tuple[str, ...]
    timeframe_minutes: int
    candles_completed: int
    journal_event_count: int
    source_runtime: str = "M20"

    def __post_init__(self) -> None:
        if self.mode != "SHADOW":
            raise ValueError("M20 manifest mode must be SHADOW")
        if self.live_broker_order_submission:
            raise ValueError("M20 manifest cannot enable live broker orders")
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if not self.symbols:
            raise ValueError("at least one symbol is required")
        if self.timeframe_minutes <= 0:
            raise ValueError("timeframe_minutes must be positive")
        if self.candles_completed < 0 or self.journal_event_count < 0:
            raise ValueError("evidence counts cannot be negative")

    def to_mapping(self) -> dict[str, Any]:
        """Return canonical JSON-safe manifest content."""
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "live_broker_order_submission": False,
            "symbols": list(self.symbols),
            "timeframe_minutes": self.timeframe_minutes,
            "candles_completed": self.candles_completed,
            "journal_event_count": self.journal_event_count,
            "source_runtime": self.source_runtime,
        }

    @property
    def fingerprint(self) -> str:
        """Return a deterministic SHA-256 identity for the manifest."""
        canonical = json.dumps(
            self.to_mapping(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    def evidence(self) -> dict[str, Any]:
        """Return manifest plus its reproducible fingerprint."""
        return {
            **self.to_mapping(),
            "manifest_fingerprint": self.fingerprint,
        }
