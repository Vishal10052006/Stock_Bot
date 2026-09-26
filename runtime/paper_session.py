"""Phase 22 chronological paper-trading session controller.

Turns the existing PaperDecisionLoop + PaperTradingRuntime +
PaperEvidenceJournal into a session-level operational boundary. It records
only observations supplied by the runtime/operator and never invents missing
latency, calibration, equity, or false-signal evidence.

No broker/network execution is exposed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from experiments.paper_journal import PaperEvidenceJournal, PaperEvidenceRecord
from trading.paper.decision_loop import PaperDecisionLoop, PaperDecisionRun


@dataclass(frozen=True, slots=True)
class PaperSessionResult:
    """Immutable result of one chronological paper session."""

    session_id: str
    started_at: datetime
    completed_at: datetime
    run: PaperDecisionRun
    evidence: PaperEvidenceRecord

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("session timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "decision_count": len(self.run.steps),
            "paper_order_count": len(self.run.orders),
            "evidence_run_id": self.evidence.run_id,
            "evidence_fingerprint": self.evidence.fingerprint,
            "live_broker_order_submission": False,
        }


class PaperSession:
    """Run one fail-closed chronological paper-trading evidence session."""

    def __init__(
        self,
        *,
        session_id: str,
        journal: PaperEvidenceJournal,
        decision_loop: PaperDecisionLoop | None = None,
        evidence_version: str = "PAPER-SESSION-v1",
        dataset_version: str = "LIVE-CHRONOLOGICAL",
        code_version: str = "UNKNOWN",
    ) -> None:
        if not session_id.strip():
            raise ValueError("session_id must not be empty")
        if not evidence_version.strip():
            raise ValueError("evidence_version must not be empty")
        if not dataset_version.strip():
            raise ValueError("dataset_version must not be empty")
        if not code_version.strip():
            raise ValueError("code_version must not be empty")

        self.session_id = session_id
        self.journal = journal
        self.decision_loop = decision_loop or PaperDecisionLoop()
        self.evidence_version = evidence_version
        self.dataset_version = dataset_version
        self.code_version = code_version
        self._started_at: datetime | None = None
        self._completed = False

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        session_id: str,
        decision_loop: PaperDecisionLoop | None = None,
        evidence_version: str = "PAPER-SESSION-v1",
        dataset_version: str = "LIVE-CHRONOLOGICAL",
        code_version: str = "UNKNOWN",
    ) -> "PaperSession":
        return cls(
            session_id=session_id,
            journal=PaperEvidenceJournal(path),
            decision_loop=decision_loop,
            evidence_version=evidence_version,
            dataset_version=dataset_version,
            code_version=code_version,
        )

    def start(self, *, now: datetime | None = None) -> datetime:
        """Start exactly once; a completed session cannot be reused."""
        if self._started_at is not None:
            raise RuntimeError("paper session already started")
        if self._completed:
            raise RuntimeError("paper session already completed")

        started = self._normalize_now(now)
        self._started_at = started
        return started

    def run(
        self,
        rows: pd.DataFrame,
        *,
        price_column: str = "close",
        quantity: float = 1.0,
        fill_timestamps: Mapping[int, object] | None = None,
        false_signals: Mapping[int, bool] | None = None,
        equity_observations: Mapping[int, float] | None = None,
        calibration_outcomes: Mapping[int, float] | None = None,
        operational_events: int = 0,
        operational_errors: int = 0,
        stale_events: int = 0,
    ) -> PaperSessionResult:
        """Run a strictly chronological paper session and persist evidence."""
        if self._started_at is None:
            self.start()
        if self._completed:
            raise RuntimeError("paper session already completed")
        if not isinstance(rows, pd.DataFrame):
            raise TypeError("rows must be a pandas DataFrame")
        if rows.empty:
            raise ValueError("paper session requires at least one row")
        if "timestamp" not in rows.columns:
            raise ValueError("rows must contain 'timestamp'")

        working = rows.copy()
        timestamps = pd.to_datetime(working["timestamp"], utc=True)
        if timestamps.isna().any():
            raise ValueError("paper session timestamps cannot be null")

        ordered = timestamps.tolist()
        if any(right < left for left, right in zip(ordered, ordered[1:])):
            raise ValueError(
                "paper session rows must be chronological; input reordering is rejected"
            )

        if "symbol" in working.columns:
            pairs = pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "symbol": working["symbol"].astype(str).str.upper(),
                }
            )
            if pairs.duplicated(["timestamp", "symbol"]).any():
                raise ValueError(
                    "duplicate timestamp for the same symbol is not allowed"
                )

        working["timestamp"] = timestamps
        run = self.decision_loop.run(
            working,
            price_column=price_column,
            quantity=quantity,
        )
        if not run.steps:
            raise ValueError("paper session produced no decisions")

        started = self._started_at
        completed = datetime.now(timezone.utc)

        from experiments.paper_journal import persist_paper_decision_run

        record = persist_paper_decision_run(
            run,
            journal=self.journal,
            source_run_id=f"{self.session_id}:{run.run_id}",
            fill_timestamps=dict(fill_timestamps or {}),
            false_signals=dict(false_signals or {}),
            equity_observations=dict(equity_observations or {}),
            calibration_outcomes=dict(calibration_outcomes or {}),
            operational_events=operational_events,
            operational_errors=operational_errors,
            stale_events=stale_events,
            evidence_version=self.evidence_version,
            dataset_version=self.dataset_version,
            code_version=self.code_version,
        )

        self._completed = True
        return PaperSessionResult(
            session_id=self.session_id,
            started_at=started,
            completed_at=completed,
            run=run,
            evidence=record,
        )

    @staticmethod
    def _normalize_now(now: datetime | None) -> datetime:
        value = now or datetime.now(timezone.utc)
        if value.tzinfo is None:
            raise ValueError("session timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)
