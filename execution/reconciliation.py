"""Broker reconciliation contracts without broker connectivity."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import json
from enum import Enum


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
        if not math.isfinite(self.quantity) or self.quantity == 0.0:
            raise ValueError("quantity must be finite and non-zero")
        if not math.isfinite(self.average_price) or self.average_price <= 0.0:
            raise ValueError("average_price must be positive and finite")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


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


class BrokerReconciler:
    """Compare authoritative local and broker position snapshots."""

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
            quantity_tolerance = 1e-12
            price_tolerance = 1e-12
            if (
                abs(left[0] - right[0]) > quantity_tolerance
                or abs(left[1] - right[1]) > price_tolerance
            ):
                mismatches.append(
                    f"{symbol}: local={left} broker={right}"
                )

        return ReconciliationReport(
            status=(
                ReconciliationStatus.MATCH
                if not mismatches
                else ReconciliationStatus.MISMATCH
            ),
            mismatches=tuple(mismatches),
        )

    @staticmethod
    def _normalize(
        positions: tuple[BrokerPosition, ...],
    ) -> dict[str, tuple[float, float]]:
        result: dict[str, tuple[float, float]] = {}
        for position in positions:
            symbol = position.symbol.strip().upper()
            if symbol in result:
                raise ValueError(f"duplicate position for {symbol}")
            result[symbol] = (
                float(position.quantity),
                float(position.average_price),
            )
        return result
