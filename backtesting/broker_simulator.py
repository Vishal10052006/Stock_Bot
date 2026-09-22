"""Deterministic broker simulator for historical backtests.

The simulator is deliberately a thin adapter over the existing paper runtime.
It does not introduce a second fill, fee, or position-accounting model.
"""

from __future__ import annotations

from dataclasses import dataclass

from execution.trading_execution import ExecutionAuthorization
from paper.runtime import (
    PaperOrder,
    PaperPosition,
    PaperTradingConfig,
    PaperTradingRuntime,
)


@dataclass(frozen=True, slots=True)
class BrokerSimulatorConfig:
    """Execution assumptions for the historical broker simulator."""

    slippage_bps: float = 5.0
    fee_bps: float = 2.0

    def __post_init__(self) -> None:
        if self.slippage_bps < 0 or self.fee_bps < 0:
            raise ValueError(
                "slippage_bps and fee_bps must be non-negative"
            )


class BrokerSimulator:
    """Broker-neutral façade over the deterministic paper runtime."""

    def __init__(
        self,
        *,
        config: BrokerSimulatorConfig | None = None,
        runtime: PaperTradingRuntime | None = None,
    ) -> None:
        if runtime is not None and config is not None:
            raise ValueError(
                "provide either config or runtime, not both"
            )

        self.runtime = runtime or PaperTradingRuntime(
            config=PaperTradingConfig(
                slippage_bps=(config.slippage_bps if config else 5.0),
                fee_bps=(config.fee_bps if config else 2.0),
            )
        )

    @property
    def journal(self) -> tuple[PaperOrder, ...]:
        """Return the immutable simulated order journal."""
        return self.runtime.journal

    def submit(
        self,
        authorization: ExecutionAuthorization,
        *,
        price: float,
        quantity: float,
    ) -> PaperOrder:
        """Simulate one authorized order."""
        return self.runtime.submit(
            authorization,
            price=price,
            quantity=quantity,
        )

    def position(self, symbol: str) -> PaperPosition | None:
        """Return the current simulated position."""
        return self.runtime.position(symbol)

    def mark_to_market(self, symbol: str, price: float) -> float:
        """Return deterministic mark-to-market P&L."""
        return self.runtime.mark_to_market(symbol, price)
