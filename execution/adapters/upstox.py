"""Upstox broker adapter boundary.

The adapter is deliberately fail-closed until a current, validated Upstox
configuration is supplied. It does not embed credentials and never attempts to
place an order without an explicit configured client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.engine import OrderRequest, OrderSnapshot, PositionSnapshot


@dataclass(frozen=True, slots=True)
class UpstoxAdapterConfig:
    """Provider-neutral metadata needed to construct a real client elsewhere."""

    api_base_url: str
    access_token_env: str = "UPSTOX_ACCESS_TOKEN"
    enabled: bool = False

    def __post_init__(self) -> None:
        if not self.api_base_url.strip():
            raise ValueError("api_base_url must not be empty")
        if not self.access_token_env.strip():
            raise ValueError("access_token_env must not be empty")


class UpstoxBrokerAdapter:
    """Explicit integration boundary for future Upstox connectivity."""

    def __init__(self, config: UpstoxAdapterConfig, client: Any | None = None) -> None:
        self.config = config
        self.client = client

    def _require_enabled(self) -> None:
        if not self.config.enabled:
            raise RuntimeError(
                "Upstox live adapter is disabled; enable only after controlled "
                "validation and current broker/compliance verification."
            )
        if self.client is None:
            raise RuntimeError(
                "No Upstox client was supplied. Credentials/client construction "
                "must remain outside the execution domain."
            )

    def submit(self, order: OrderRequest) -> OrderSnapshot:
        self._require_enabled()
        raise NotImplementedError(
            "Provider-specific Upstox request mapping must be implemented and "
            "verified against the current Upstox API contract before live use."
        )

    def get_order(self, client_order_id: str) -> OrderSnapshot | None:
        self._require_enabled()
        raise NotImplementedError

    def cancel(self, client_order_id: str) -> OrderSnapshot:
        self._require_enabled()
        raise NotImplementedError

    def positions(self) -> tuple[PositionSnapshot, ...]:
        self._require_enabled()
        raise NotImplementedError


__all__ = ["UpstoxAdapterConfig", "UpstoxBrokerAdapter"]