"""Broker reconciliation contracts without broker connectivity.

Reconciliation is observation-only and fail-closed. A MATCH report means the
provided local and authoritative broker snapshots agree within explicit
numeric tolerances; it never grants live execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math


class ReconciliationStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    symbol: str
    quantity: float
    average_price: float

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not math.isfinite(float(self.quantity)):
            raise ValueError("quantity must be finite")
        if not math.isfinite(float(self.average_price)):
            raise ValueError("average_price must be finite")
        if self.average_price < 0:
            raise ValueError("average_price must be non-negative")
        # Signed quantity: positive=long, negative=short.
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


@dataclass(frozen=True, slots=True)
class ReconciliationConfig:
    """Explicit tolerances for provider rounding differences."""

    quantity_tolerance: float = 1e-12
    price_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        if not math.isfinite(self.quantity_tolerance) or self.quantity_tolerance < 0:
            raise ValueError("quantity_tolerance must be finite and non-negative")
        if not math.isfinite(self.price_tolerance) or self.price_tolerance < 0:
            raise ValueError("price_tolerance must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    status: ReconciliationStatus
    mismatches: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        payload = {"status": self.status.value, "mismatches": self.mismatches}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def safe(self) -> bool:
        return self.status is ReconciliationStatus.MATCH

    @property
    def requires_intervention(self) -> bool:
        return self.status is not ReconciliationStatus.MATCH


class BrokerReconciler:
    """Compare local and authoritative broker position snapshots."""

    def __init__(self, config: ReconciliationConfig | None = None) -> None:
        self.config = config or ReconciliationConfig()

    def reconcile(
        self,
        local: tuple[BrokerPosition, ...] | None,
        broker: tuple[BrokerPosition, ...] | None,
    ) -> ReconciliationReport:
        if local is None or broker is None:
            return ReconciliationReport(
                status=ReconciliationStatus.BLOCKED,
                mismatches=("local and broker snapshots are both required",),
            )

        local_map = self._normalize(local)
        broker_map = self._normalize(broker)
        symbols = sorted(set(local_map) | set(broker_map))
        mismatches: list[str] = []

        for symbol in symbols:
            left = local_map.get(symbol, (0.0, 0.0))
            right = broker_map.get(symbol, (0.0, 0.0))
            if not self._matches(left, right):
                mismatches.append(f"{symbol}: local={left} broker={right}")

        return ReconciliationReport(
            status=(
                ReconciliationStatus.MATCH
                if not mismatches
                else ReconciliationStatus.MISMATCH
            ),
            mismatches=tuple(mismatches),
        )

    def _matches(
        self,
        left: tuple[float, float],
        right: tuple[float, float],
    ) -> bool:
        return (
            math.isclose(
                left[0],
                right[0],
                rel_tol=0.0,
                abs_tol=self.config.quantity_tolerance,
            )
            and math.isclose(
                left[1],
                right[1],
                rel_tol=0.0,
                abs_tol=self.config.price_tolerance,
            )
        )

    @staticmethod
    def _normalize(
        positions: tuple[BrokerPosition, ...],
    ) -> dict[str, tuple[float, float]]:
        result: dict[str, tuple[float, float]] = {}
        for position in positions:
            if not isinstance(position, BrokerPosition):
                raise TypeError("positions must contain BrokerPosition values")
            symbol = position.symbol.strip().upper()
            if symbol in result:
                raise ValueError(f"duplicate position for {symbol}")
            result[symbol] = (
                float(position.quantity),
                float(position.average_price),
            )
        return result


__all__ = [
    "BrokerPosition",
    "BrokerReconciler",
    "ReconciliationConfig",
    "ReconciliationReport",
    "ReconciliationStatus",
]
