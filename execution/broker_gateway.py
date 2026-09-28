"""Phase 25 broker boundary: locked gateway and sandbox-capable adapter contract.

This module deliberately does not submit live broker orders. It provides the
typed integration seam and a fail-closed gateway so broker credentials cannot
turn the research/paper runtime into live execution accidentally.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from execution.engine import BrokerAdapter, OrderRequest, OrderSnapshot, PositionSnapshot


class BrokerMode(str, Enum):
    SANDBOX="SANDBOX"
    LIVE="LIVE"


class BrokerIntegrationLocked(RuntimeError):
    """Raised whenever a live broker operation is attempted while locked."""


@dataclass(frozen=True, slots=True)
class BrokerGatewayConfig:
    mode: BrokerMode = BrokerMode.SANDBOX
    live_order_submission: bool = False

    def __post_init__(self) -> None:
        if self.mode is BrokerMode.LIVE or self.live_order_submission:
            raise BrokerIntegrationLocked(
                "Phase 25 live broker order submission is locked pending readiness gates."
            )


class LockedBrokerGateway:
    """BrokerAdapter seam that permits no live network/order authority."""

    def __init__(self, adapter: BrokerAdapter, *, config: BrokerGatewayConfig | None = None) -> None:
        self.adapter=adapter
        self.config=config or BrokerGatewayConfig()

    def submit(self, order: OrderRequest) -> OrderSnapshot:
        raise BrokerIntegrationLocked(
            "Live broker submission is disabled. Use PaperTradingRuntime or a sandbox adapter."
        )

    def get_order(self, client_order_id: str) -> OrderSnapshot | None:
        raise BrokerIntegrationLocked("Live broker state access is locked in Phase 25.")

    def cancel(self, client_order_id: str) -> OrderSnapshot:
        raise BrokerIntegrationLocked("Live broker cancellation is locked in Phase 25.")

    def positions(self) -> tuple[PositionSnapshot, ...]:
        raise BrokerIntegrationLocked("Live broker position access is locked in Phase 25.")

    def evidence(self) -> dict[str, object]:
        return {
            "mode": self.config.mode.value,
            "live_broker_order_submission": False,
            "broker_network_authority": False,
            "status": "LOCKED",
        }


__all__=["BrokerGatewayConfig","BrokerIntegrationLocked","LockedBrokerGateway","BrokerMode"]
