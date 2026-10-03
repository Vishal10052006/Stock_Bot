"""V1 manual-review evidence journal.

This module records the human review boundary for the canonical V1 signal.
It is observation/memory only: it never places, modifies, cancels, or infers
broker orders or trade outcomes.

Each review is immutable and append-only. A later manual outcome is a separate
event so an accepted signal is never silently treated as an executed trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Union

from v1_signal.contracts import V1SignalContract


class ManualReviewAction(str, Enum):
    """Explicit human review result."""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class ManualOutcomeStatus(str, Enum):
    """Observed manual-trade lifecycle result."""

    EXECUTED = "EXECUTED"
    NOT_EXECUTED = "NOT_EXECUTED"
    CLOSED = "CLOSED"


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("manual-review numeric values must be finite")
        return value
    if hasattr(value, "item"):
        return _json_value(value.item())
    raise TypeError(f"unsupported manual-review value type: {type(value).__name__}")


def _fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class ManualReviewRecord:
    """Immutable record of a human review of one canonical V1 signal."""

    review_id: str
    signal_id: str
    signal_fingerprint: str
    reviewed_at: datetime
    symbol: str
    signal: str
    signal_timestamp: datetime
    valid_until: datetime
    entry: float | None
    stop_loss: float | None
    target: float | None
    risk_reward: float | None
    confidence: float | None
    prediction_evidence: Mapping[str, Any]
    supporting_factors: tuple[str, ...]
    contradicting_factors: tuple[str, ...]
    risk_conditions: tuple[str, ...]
    provenance: Mapping[str, str]
    action: ManualReviewAction
    review_note: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("reviewed_at", self.reviewed_at),
            ("signal_timestamp", self.signal_timestamp),
            ("valid_until", self.valid_until),
        ):
            if value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if not self.review_id.strip() or not self.signal_id.strip():
            raise ValueError("review_id and signal_id must not be empty")
        if not self.signal_fingerprint.strip():
            raise ValueError("signal_fingerprint must not be empty")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.signal not in {"BUY", "SELL", "WAIT"}:
            raise ValueError("invalid V1 signal")
        if self.valid_until < self.signal_timestamp:
            raise ValueError("valid_until must not precede signal_timestamp")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.risk_reward is not None and float(self.risk_reward) < 0:
            raise ValueError("risk_reward must be non-negative")
        for name, value in (
            ("entry", self.entry),
            ("stop_loss", self.stop_loss),
            ("target", self.target),
            ("risk_reward", self.risk_reward),
            ("confidence", self.confidence),
        ):
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "prediction_evidence", dict(self.prediction_evidence))
        object.__setattr__(self, "supporting_factors", tuple(self.supporting_factors))
        object.__setattr__(self, "contradicting_factors", tuple(self.contradicting_factors))
        object.__setattr__(self, "risk_conditions", tuple(self.risk_conditions))
        object.__setattr__(self, "provenance", dict(self.provenance))

    @classmethod
    def from_signal(
        cls,
        signal: V1SignalContract,
        *,
        action: ManualReviewAction,
        reviewed_at: datetime,
        review_note: str = "",
    ) -> "ManualReviewRecord":
        """Capture exactly what the human saw; never reconstruct it later."""
        if not isinstance(signal, V1SignalContract):
            raise TypeError("signal must be a V1SignalContract")
        if reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")

        payload = {
            "signal_id": signal.signal_id,
            "signal_fingerprint": signal.as_dict()["fingerprint"],
            "reviewed_at": reviewed_at.isoformat(),
            "symbol": signal.symbol,
            "signal": signal.signal.value,
            "signal_timestamp": signal.timestamp.isoformat(),
            "valid_until": signal.valid_until.isoformat(),
            "entry": signal.entry,
            "stop_loss": signal.stop_loss,
            "target": signal.target,
            "risk_reward": signal.risk_reward,
            "confidence": signal.confidence,
            "prediction_evidence": signal.prediction_evidence,
            "supporting_factors": signal.supporting_factors,
            "contradicting_factors": signal.contradicting_factors,
            "risk_conditions": signal.risk_conditions,
            "provenance": signal.provenance,
            "action": action.value,
            "review_note": review_note,
        }
        review_id = "REV-" + _fingerprint(payload)[:24]
        return cls(
            review_id=review_id,
            signal_id=signal.signal_id,
            signal_fingerprint=payload["signal_fingerprint"],
            reviewed_at=reviewed_at,
            symbol=signal.symbol,
            signal=signal.signal.value,
            signal_timestamp=signal.timestamp.to_pydatetime(),
            valid_until=signal.valid_until.to_pydatetime(),
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            target=signal.target,
            risk_reward=signal.risk_reward,
            confidence=signal.confidence,
            prediction_evidence=signal.prediction_evidence,
            supporting_factors=signal.supporting_factors,
            contradicting_factors=signal.contradicting_factors,
            risk_conditions=signal.risk_conditions,
            provenance=signal.provenance,
            action=action,
            review_note=review_note,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["record_type"] = "manual_review"
        return _json_value(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ManualReviewRecord":
        required = {
            "review_id", "signal_id", "signal_fingerprint", "reviewed_at",
            "symbol", "signal", "signal_timestamp", "valid_until", "entry",
            "stop_loss", "target", "risk_reward", "confidence",
            "prediction_evidence", "supporting_factors", "contradicting_factors",
            "risk_conditions", "provenance", "action",
        }
        missing = required.difference(data)
        if missing:
            raise ValueError(f"manual review missing required fields: {sorted(missing)}")
        return cls(
            review_id=str(data["review_id"]),
            signal_id=str(data["signal_id"]),
            signal_fingerprint=str(data["signal_fingerprint"]),
            reviewed_at=datetime.fromisoformat(str(data["reviewed_at"])),
            symbol=str(data["symbol"]),
            signal=str(data["signal"]),
            signal_timestamp=datetime.fromisoformat(str(data["signal_timestamp"])),
            valid_until=datetime.fromisoformat(str(data["valid_until"])),
            entry=None if data["entry"] is None else float(data["entry"]),
            stop_loss=None if data["stop_loss"] is None else float(data["stop_loss"]),
            target=None if data["target"] is None else float(data["target"]),
            risk_reward=None if data["risk_reward"] is None else float(data["risk_reward"]),
            confidence=None if data["confidence"] is None else float(data["confidence"]),
            prediction_evidence=dict(data["prediction_evidence"]),
            supporting_factors=tuple(data["supporting_factors"]),
            contradicting_factors=tuple(data["contradicting_factors"]),
            risk_conditions=tuple(data["risk_conditions"]),
            provenance=dict(data["provenance"]),
            action=ManualReviewAction(str(data["action"])),
            review_note=str(data.get("review_note", "")),
        )


@dataclass(frozen=True, slots=True)
class ManualOutcomeRecord:
    """Immutable user-reported outcome; the bot never creates one automatically."""

    outcome_id: str
    review_id: str
    signal_id: str
    observed_at: datetime
    status: ManualOutcomeStatus
    execution_timestamp: datetime | None
    entry_price: float | None
    exit_timestamp: datetime | None
    exit_price: float | None
    quantity: float | None
    fees: float | None
    slippage_cost: float | None
    net_pnl: float | None
    note: str = ""

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.execution_timestamp is not None and self.execution_timestamp.tzinfo is None:
            raise ValueError("execution_timestamp must be timezone-aware")
        if self.exit_timestamp is not None and self.exit_timestamp.tzinfo is None:
            raise ValueError("exit_timestamp must be timezone-aware")
        if not self.review_id.strip() or not self.signal_id.strip():
            raise ValueError("review_id and signal_id must not be empty")
        for name, value in (
            ("entry_price", self.entry_price),
            ("exit_price", self.exit_price),
            ("quantity", self.quantity),
            ("fees", self.fees),
            ("slippage_cost", self.slippage_cost),
            ("net_pnl", self.net_pnl),
        ):
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.fees is not None and self.fees < 0:
            raise ValueError("fees must be non-negative")
        if self.slippage_cost is not None and self.slippage_cost < 0:
            raise ValueError("slippage_cost must be non-negative")
        if self.status in {ManualOutcomeStatus.EXECUTED, ManualOutcomeStatus.CLOSED}:
            if self.execution_timestamp is None or self.entry_price is None or self.quantity is None:
                raise ValueError("executed outcomes require execution timestamp, entry price, and quantity")
        if self.status is ManualOutcomeStatus.CLOSED:
            if self.exit_timestamp is None or self.exit_price is None or self.net_pnl is None:
                raise ValueError("closed outcomes require exit timestamp, exit price, and net_pnl")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["record_type"] = "manual_outcome"
        return _json_value(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ManualOutcomeRecord":
        required = {
            "outcome_id", "review_id", "signal_id", "observed_at", "status",
            "execution_timestamp", "entry_price", "exit_timestamp", "exit_price",
            "quantity", "fees", "slippage_cost", "net_pnl",
        }
        missing = required.difference(data)
        if missing:
            raise ValueError(f"manual outcome missing required fields: {sorted(missing)}")
        return cls(
            outcome_id=str(data["outcome_id"]),
            review_id=str(data["review_id"]),
            signal_id=str(data["signal_id"]),
            observed_at=datetime.fromisoformat(str(data["observed_at"])),
            status=ManualOutcomeStatus(str(data["status"])),
            execution_timestamp=(
                None if data["execution_timestamp"] is None
                else datetime.fromisoformat(str(data["execution_timestamp"]))
            ),
            entry_price=None if data["entry_price"] is None else float(data["entry_price"]),
            exit_timestamp=(
                None if data["exit_timestamp"] is None
                else datetime.fromisoformat(str(data["exit_timestamp"]))
            ),
            exit_price=None if data["exit_price"] is None else float(data["exit_price"]),
            quantity=None if data["quantity"] is None else float(data["quantity"]),
            fees=None if data["fees"] is None else float(data["fees"]),
            slippage_cost=None if data["slippage_cost"] is None else float(data["slippage_cost"]),
            net_pnl=None if data["net_pnl"] is None else float(data["net_pnl"]),
            note=str(data.get("note", "")),
        )


ManualReviewEvent = Union[ManualReviewRecord, ManualOutcomeRecord]


class ManualReviewStore:
    """Append-only JSONL store for human review and manually reported outcomes."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: ManualReviewEvent) -> None:
        if not isinstance(record, (ManualReviewRecord, ManualOutcomeRecord)):
            raise TypeError("record must be a ManualReviewRecord or ManualOutcomeRecord")
        key = (record.__class__.__name__, getattr(record, "review_id", None), getattr(record, "outcome_id", None))
        existing = {
            (
                item.__class__.__name__,
                getattr(item, "review_id", None),
                getattr(item, "outcome_id", None),
            )
            for item in self.read_events()
        }
        if key in existing:
            raise ValueError("duplicate manual-review event")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    def read_events(self) -> tuple[ManualReviewEvent, ...]:
        if not self.path.exists():
            return ()
        records: list[ManualReviewEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    record_type = data.get("record_type")
                    if record_type == "manual_review":
                        records.append(ManualReviewRecord.from_dict(data))
                    elif record_type == "manual_outcome":
                        records.append(ManualOutcomeRecord.from_dict(data))
                    else:
                        raise ValueError(f"unknown record_type {record_type!r}")
                except Exception as exc:
                    raise ValueError(f"invalid manual-review record at line {line_number}") from exc
        return tuple(records)

    def reviews(self) -> tuple[ManualReviewRecord, ...]:
        return tuple(item for item in self.read_events() if isinstance(item, ManualReviewRecord))

    def outcomes(self) -> tuple[ManualOutcomeRecord, ...]:
        return tuple(item for item in self.read_events() if isinstance(item, ManualOutcomeRecord))

    def outcome_for_review(self, review_id: str) -> ManualOutcomeRecord | None:
        matches = tuple(item for item in self.outcomes() if item.review_id == review_id)
        if len(matches) > 1:
            raise ValueError(f"multiple manual outcomes found for review_id {review_id}")
        return matches[0] if matches else None


class ManualReviewJournal:
    """High-level API for recording human review and later observations."""

    def __init__(self, store: ManualReviewStore) -> None:
        self.store = store

    def record_review(
        self,
        signal: V1SignalContract,
        *,
        action: ManualReviewAction,
        reviewed_at: datetime,
        review_note: str = "",
    ) -> ManualReviewRecord:
        record = ManualReviewRecord.from_signal(
            signal,
            action=action,
            reviewed_at=reviewed_at,
            review_note=review_note,
        )
        self.store.append(record)
        return record

    def record_outcome(self, outcome: ManualOutcomeRecord) -> ManualOutcomeRecord:
        """Persist only a caller-supplied/manual observation."""
        self.store.append(outcome)
        return outcome

    def reviews(self) -> tuple[ManualReviewRecord, ...]:
        return self.store.reviews()

    def outcomes(self) -> tuple[ManualOutcomeRecord, ...]:
        return self.store.outcomes()


__all__ = [
    "ManualOutcomeRecord",
    "ManualOutcomeStatus",
    "ManualReviewAction",
    "ManualReviewEvent",
    "ManualReviewJournal",
    "ManualReviewRecord",
    "ManualReviewStore",
]
