"""Observation-only stock scanner for the STOCK_BOT operator surface.

The scanner consumes already-authoritative Prediction/Strategy/Risk outputs.
It never creates trade authority, changes strategy/risk state, submits orders,
or enables live execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


def _get(source: Any, key: str, default: Any = None) -> Any:
    """Read one field from a mapping or attribute-based contract."""
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _timestamp(value: Any) -> str:
    """Normalize a timestamp and reject timezone-naive values."""
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("scanner timestamp is invalid") from exc
    if ts.tzinfo is None:
        raise ValueError("scanner timestamp must be timezone-aware")
    return ts.isoformat()


def _finite(value: Any, field_name: str) -> float:
    """Convert a numeric value and reject NaN/inf."""
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _probabilities(prediction: Any) -> tuple[float, float, float]:
    """Extract canonical LONG_SUCCESS/SHORT_SUCCESS/NO_EDGE probabilities."""
    table = _get(prediction, "probabilities")
    if table is not None and hasattr(table, "iloc"):
        if len(table) != 1:
            raise ValueError("prediction probabilities must contain one row")
        row = table.iloc[0]
        values = (
            row.get("LONG_SUCCESS"),
            row.get("SHORT_SUCCESS"),
            row.get("NO_EDGE"),
        )
    else:
        values = (
            _get(prediction, "long_probability", _get(prediction, "p_long")),
            _get(prediction, "short_probability", _get(prediction, "p_short")),
            _get(prediction, "no_edge_probability", _get(prediction, "p_no_edge")),
        )

    result = tuple(
        _finite(value, name)
        for value, name in zip(
            values, ("long_success", "short_success", "no_edge")
        )
    )
    if any(value < 0.0 or value > 1.0 for value in result):
        raise ValueError("prediction probabilities must lie in [0, 1]")
    if not math.isclose(sum(result), 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("prediction probabilities must sum to 1")
    return result


@dataclass(frozen=True, slots=True)
class StockScannerRow:
    """One latest, auditable symbol state for the operator."""

    timestamp: str
    symbol: str
    price: float | None
    long_success: float
    short_success: float
    no_edge: float
    predicted_class: str
    regime: str | None
    strategy: str
    strategy_reason: str
    risk_status: str
    risk_reason: str
    paper_order_status: str | None
    trade_id: str | None
    entry_reference: float | None
    stop_reference: float | None
    target_reference: float | None
    prediction_model_version: str
    calibration_version: str | None
    feature_version: str
    signal_strength: float
    authority: str = "OBSERVATION_ONLY"
    provenance: Mapping[str, Any] = field(default_factory=dict)
    # V1 human-review fields consumed directly by the dashboard.
    display_signal: str = "WAIT"
    confidence: float | None = None
    valid_until: str | None = None
    v1_fingerprint: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _timestamp(self.timestamp))
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("scanner symbol must not be empty")
        object.__setattr__(self, "symbol", symbol)

        if self.predicted_class not in {
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        }:
            raise ValueError("scanner predicted_class is invalid")
        if self.strategy not in {"LONG", "SHORT", "NO_TRADE"}:
            raise ValueError("scanner strategy is invalid")
        if any(
            value < 0.0 or value > 1.0
            for value in (self.long_success, self.short_success, self.no_edge)
        ):
            raise ValueError("scanner probabilities must lie in [0, 1]")
        if not math.isclose(
            self.long_success + self.short_success + self.no_edge,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            raise ValueError("scanner probabilities must sum to 1")
        if not -1.0 <= self.signal_strength <= 1.0:
            raise ValueError("scanner signal_strength must be in [-1, 1]")
        if self.authority != "OBSERVATION_ONLY":
            raise ValueError("scanner is observation-only")
        if self.display_signal not in {"BUY", "SELL", "WAIT"}:
            raise ValueError("scanner display_signal is invalid")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("scanner confidence must be in [0, 1]")
        if self.valid_until is not None:
            _timestamp(self.valid_until)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible payload."""
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class StockScannerSnapshot:
    """Deterministic latest-per-symbol scanner snapshot."""

    timestamp: str | None
    rows: tuple[StockScannerRow, ...]
    status: str
    authority: str = "OBSERVATION_ONLY"
    source: str = "canonical_prediction_strategy_risk"
    fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"READY", "NO_DATA", "INVALID"}:
            raise ValueError("invalid scanner snapshot status")
        if self.authority != "OBSERVATION_ONLY":
            raise ValueError("scanner snapshot authority must remain observational")
        object.__setattr__(
            self,
            "rows",
            tuple(
                sorted(
                    self.rows,
                    key=lambda item: (-item.signal_strength, item.symbol),
                )
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic snapshot with a SHA-256 fingerprint."""
        payload = {
            "timestamp": self.timestamp,
            "rows": [row.as_dict() for row in self.rows],
            "status": self.status,
            "authority": self.authority,
            "source": self.source,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["fingerprint"] = (
            self.fingerprint
            or hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )
        return payload


class StockScannerStore:
    """Keep the latest causal observation for each symbol."""

    def __init__(self) -> None:
        self._rows: dict[str, StockScannerRow] = {}

    @property
    def rows(self) -> tuple[StockScannerRow, ...]:
        """Return latest state sorted by descriptive signal strength."""
        return tuple(
            sorted(
                self._rows.values(),
                key=lambda item: (-item.signal_strength, item.symbol),
            )
        )

    def observe(
        self,
        decision: Any,
        *,
        price: float | None = None,
    ) -> StockScannerRow:
        """Record one canonical prediction/strategy/risk observation."""
        # Prefer the canonical V1 contract when present. The scanner remains
        # observational: it only projects already-authoritative fields.
        v1_signal = _get(decision, "v1_signal")
        if v1_signal is None and hasattr(decision, "signal") and hasattr(decision, "valid_until"):
            v1_signal = decision

        prediction = _get(decision, "prediction")
        strategy = _get(decision, "strategy")

        if v1_signal is not None:
            timestamp = _timestamp(_get(v1_signal, "timestamp"))
            symbol = str(_get(v1_signal, "symbol", "")).strip().upper()
            raw_signal = _get(v1_signal, "signal", "WAIT")
            display_signal = str(getattr(raw_signal, "value", raw_signal))
            confidence = _get(v1_signal, "confidence")
            valid_until = _timestamp(_get(v1_signal, "valid_until"))
            fingerprint = _get(v1_signal, "fingerprint")
            provenance = _get(v1_signal, "provenance", {})
        else:
            if prediction is None or strategy is None:
                raise ValueError("decision must contain prediction and strategy")
            timestamp = _timestamp(_get(prediction, "timestamp"))
            symbol = str(
                _get(prediction, "symbol", _get(strategy, "symbol", ""))
            ).strip().upper()
            raw_direction = _get(strategy, "direction", "NO_TRADE")
            direction = str(getattr(raw_direction, "value", raw_direction))
            display_signal = (
                "BUY" if direction == "LONG"
                else "SELL" if direction == "SHORT"
                else "WAIT"
            )
            confidence = _get(strategy, "prediction_probability")
            valid_until = None
            fingerprint = None
            provenance = _get(prediction, "provenance", {})

        if not symbol:
            raise ValueError("decision symbol is required")

        existing = self._rows.get(symbol)
        if existing is not None and pd.Timestamp(timestamp) < pd.Timestamp(
            existing.timestamp
        ):
            raise ValueError("scanner decision timestamp moved backwards")

        if prediction is not None:
            long_p, short_p, no_edge = _probabilities(prediction)
            predicted_class = str(_get(prediction, "predicted_class", "")).strip()
        else:
            long_p, short_p, no_edge = (
                (1.0, 0.0, 0.0) if display_signal == "BUY"
                else (0.0, 1.0, 0.0) if display_signal == "SELL"
                else (0.0, 0.0, 1.0)
            )
            predicted_class = (
                "LONG_SUCCESS" if display_signal == "BUY"
                else "SHORT_SUCCESS" if display_signal == "SELL"
                else "NO_EDGE"
            )
        if predicted_class not in {
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        }:
            predicted_class = (
                "LONG_SUCCESS"
                if long_p >= max(short_p, no_edge)
                else "SHORT_SUCCESS"
                if short_p >= no_edge
                else "NO_EDGE"
            )

        direction = _get(strategy, "direction", "NO_TRADE")
        strategy_value = str(getattr(direction, "value", direction))
        strategy_reason = str(_get(strategy, "rationale", ""))

        # When the canonical V1 contract is supplied directly, project its
        # authoritative review fields instead of inventing strategy values.
        if v1_signal is not None:
            strategy_value = (
                "LONG" if display_signal == "BUY"
                else "SHORT" if display_signal == "SELL"
                else "NO_TRADE"
            )
            strategy_reason = str(
                _get(v1_signal, "supporting_factors", ())
                or _get(v1_signal, "risk_conditions", ())
                or "Canonical V1 human-review signal."
            )
            v1_entry = _get(v1_signal, "entry")
            v1_stop = _get(v1_signal, "stop_loss")
            v1_target = _get(v1_signal, "target")
            v1_risk_status = (
                "APPROVED" if display_signal in {"BUY", "SELL"} else "WAIT"
            )
        else:
            v1_entry = None
            v1_stop = None
            v1_target = None
            v1_risk_status = None

        row = StockScannerRow(
            timestamp=timestamp,
            symbol=symbol,
            price=None if price is None else _finite(price, "price"),
            long_success=long_p,
            short_success=short_p,
            no_edge=no_edge,
            predicted_class=predicted_class,
            regime=_get(strategy, "regime"),
            strategy=strategy_value,
            strategy_reason=strategy_reason,
            risk_status=str(
                _get(decision, "risk_status", v1_risk_status or "UNKNOWN")
            ),
            risk_reason=str(
                _get(decision, "risk_reason", "")
                or (_get(v1_signal, "risk_conditions", ()) if v1_signal is not None else "")
            ),
            paper_order_status=_get(decision, "paper_order_status"),
            trade_id=_get(decision, "trade_id"),
            entry_reference=_numeric_or_none(
                _get(strategy, "entry_reference", v1_entry)
            ),
            stop_reference=_numeric_or_none(
                _get(strategy, "stop_reference", v1_stop)
            ),
            target_reference=_numeric_or_none(
                _get(strategy, "target_reference", v1_target)
            ),
            prediction_model_version=str(
                _get(prediction, "model_version", "unknown")
            ),
            calibration_version=_get(prediction, "calibration_version"),
            feature_version=str(
                _get(prediction, "feature_version", "unknown")
            ),
            signal_strength=max(
                -1.0,
                min(1.0, max(long_p, short_p) - no_edge),
            ),
            provenance=provenance,
            display_signal=display_signal,
            confidence=None if confidence is None else _finite(confidence, "confidence"),
            valid_until=valid_until,
            v1_fingerprint=fingerprint,
        )
        self._rows[symbol] = row
        return row

    def as_dict(self) -> dict[str, Any]:
        """Return the current latest-per-symbol snapshot."""
        return self.snapshot().as_dict()

    def snapshot(self) -> StockScannerSnapshot:
        """Build a deterministic latest-per-symbol snapshot."""
        rows = self.rows
        latest = max(
            (pd.Timestamp(row.timestamp) for row in rows),
            default=None,
        )
        return StockScannerSnapshot(
            timestamp=None if latest is None else latest.isoformat(),
            rows=rows,
            status="READY" if rows else "NO_DATA",
        )

    def write_json(
        self,
        path: Path,
        *,
        mode: str = "live_market_paper",
    ) -> StockScannerSnapshot:
        """Atomically persist an observation-only operator snapshot.

        ``mode`` is explicit so the scanner never silently relabels a
        real-market manual-review runtime as a paper session.
        """
        snapshot = self.snapshot()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not mode.strip():
            raise ValueError("snapshot mode must not be empty")

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode.strip(),
            "authority": "OBSERVATION_ONLY",
            "focus_symbol": snapshot.rows[0].symbol if snapshot.rows else None,
            "views": {"scanner": snapshot.as_dict()},
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["fingerprint"] = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return snapshot


def _numeric_or_none(value: Any) -> float | None:
    """Normalize optional numeric references without inventing defaults."""
    if value is None:
        return None
    return _finite(value, "strategy_reference")


def _json(value: Any) -> Any:
    """Convert dataclass/NumPy/Pandas values into JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _json(value.item())
        except Exception:
            pass
    return str(value)


__all__ = ["StockScannerRow", "StockScannerSnapshot", "StockScannerStore"]
