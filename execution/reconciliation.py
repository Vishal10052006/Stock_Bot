"""Broker reconciliation contracts without broker connectivity."""

from __future__ import annotations

from dataclasses import dataclass
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
        if self.quantity < 0:
            raise ValueError("quantity must not be negative")
        if self.average_price < 0:
            raise ValueError("average_price must not be negative")


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    status: ReconciliationStatus
    mismatches: tuple[str, ...]

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
            if left != right:
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
