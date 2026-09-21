"""AB-40 deterministic fill and slippage model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from trading.strategy.models import StrategyDirection


class FillType(str, Enum):
    MARKET = "MARKET"


@dataclass(frozen=True, slots=True)
class FillConfig:
    """Execution assumptions used by historical simulation."""

    slippage_bps: float = 5.0
    fill_type: FillType = FillType.MARKET

    def __post_init__(self) -> None:
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    """Immutable simulated execution result."""

    requested_price: float
    fill_price: float
    quantity: float
    slippage_cost: float
    fill_type: FillType


class FillModel:
    """Deterministic directional slippage model."""

    def __init__(self, config: FillConfig | None = None) -> None:
        self.config = config or FillConfig()

    def fill(
        self,
        *,
        price: float,
        quantity: float,
        direction: StrategyDirection,
    ) -> SimulatedFill:
        if price <= 0:
            raise ValueError("price must be positive")

        if quantity <= 0:
            raise ValueError("quantity must be positive")

        if direction is StrategyDirection.NO_TRADE:
            raise ValueError("NO_TRADE cannot be filled")

        rate = self.config.slippage_bps / 10_000.0

        if direction is StrategyDirection.LONG:
            fill_price = price * (1.0 + rate)
        else:
            fill_price = price * (1.0 - rate)

        # Calculate monetary slippage from the requested notional
        # and configured basis-point rate. This avoids avoidable
        # floating-point subtraction error in the cost ledger.
        slippage_cost = price * quantity * rate

        return SimulatedFill(
            requested_price=price,
            fill_price=fill_price,
            quantity=quantity,
            slippage_cost=slippage_cost,
            fill_type=self.config.fill_type,
        )
