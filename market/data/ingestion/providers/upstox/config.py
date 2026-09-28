"""Configuration for the Upstox provider boundary.

Secrets are loaded only from the process environment. The provider defaults
to SANDBOX and explicitly rejects live order authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_SUPPORTED_ENVIRONMENTS = frozenset({"SANDBOX"})


@dataclass(frozen=True, slots=True)
class UpstoxFeedConfig:
    """Validated Upstox runtime configuration."""

    access_token: str
    mode: str = "ltpc"
    timeout_seconds: float = 10.0
    reconnect_max_attempts: int = 3
    reconnect_delay_seconds: float = 1.0
    environment: str = "SANDBOX"
    live_order_submission: bool = False
    client_id: str | None = None

    def __post_init__(self) -> None:
        if not self.access_token.strip():
            raise ValueError("UPSTOX_ACCESS_TOKEN is required")
        environment = self.environment.strip().upper()
        if environment not in _SUPPORTED_ENVIRONMENTS:
            raise ValueError(
                "Upstox provider environment must be SANDBOX; live integration remains locked"
            )
        if self.live_order_submission:
            raise ValueError(
                "UPSTOX live order submission is locked and must remain false"
            )
        if self.client_id is not None and not self.client_id.strip():
            raise ValueError("UPSTOX_CLIENT_ID must not be empty when supplied")
        if self.timeout_seconds <= 0:
            raise ValueError("UPSTOX_FEED_TIMEOUT_SECONDS must be > 0")
        if self.reconnect_max_attempts < 0:
            raise ValueError("UPSTOX_RECONNECT_MAX_ATTEMPTS must be >= 0")
        if self.reconnect_delay_seconds < 0:
            raise ValueError("UPSTOX_RECONNECT_DELAY_SECONDS must be >= 0")
        object.__setattr__(self, "environment", environment)

    @classmethod
    def from_env(cls) -> "UpstoxFeedConfig":
        """Build a fail-closed configuration from environment variables."""
        access_token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
        if not access_token:
            raise ValueError("UPSTOX_ACCESS_TOKEN is required")

        environment = os.getenv("STOCK_BOT_UPSTOX_MODE", "SANDBOX").strip().upper()
        if environment not in _SUPPORTED_ENVIRONMENTS:
            raise ValueError(
                "STOCK_BOT_UPSTOX_MODE must be SANDBOX; live integration remains locked"
            )

        live_raw = os.getenv(
            "STOCK_BOT_LIVE_ORDER_SUBMISSION", "false"
        ).strip().lower()
        if live_raw in _TRUE_VALUES:
            raise ValueError("STOCK_BOT_LIVE_ORDER_SUBMISSION must remain false")

        mode = os.getenv("UPSTOX_FEED_MODE", "ltpc").strip().lower()
        if mode not in {"ltpc", "full", "option_greeks", "full_d30"}:
            raise ValueError(f"Unsupported UPSTOX_FEED_MODE: {mode}")

        try:
            timeout_seconds = float(os.getenv("UPSTOX_FEED_TIMEOUT_SECONDS", "10"))
        except ValueError as exc:
            raise ValueError("UPSTOX_FEED_TIMEOUT_SECONDS must be numeric") from exc

        try:
            reconnect_max_attempts = int(
                os.getenv("UPSTOX_RECONNECT_MAX_ATTEMPTS", "3")
            )
        except ValueError as exc:
            raise ValueError(
                "UPSTOX_RECONNECT_MAX_ATTEMPTS must be an integer"
            ) from exc

        try:
            reconnect_delay_seconds = float(
                os.getenv("UPSTOX_RECONNECT_DELAY_SECONDS", "1")
            )
        except ValueError as exc:
            raise ValueError(
                "UPSTOX_RECONNECT_DELAY_SECONDS must be numeric"
            ) from exc

        return cls(
            access_token=access_token,
            mode=mode,
            timeout_seconds=timeout_seconds,
            reconnect_max_attempts=reconnect_max_attempts,
            reconnect_delay_seconds=reconnect_delay_seconds,
            environment=environment,
            live_order_submission=False,
            client_id=os.getenv("UPSTOX_CLIENT_ID", "").strip() or None,
        )

    def evidence(self) -> dict[str, object]:
        """Return non-secret operational evidence."""
        return {
            "provider": "upstox",
            "environment": self.environment,
            "feed_mode": self.mode,
            "timeout_seconds": self.timeout_seconds,
            "reconnect_max_attempts": self.reconnect_max_attempts,
            "reconnect_delay_seconds": self.reconnect_delay_seconds,
            "client_id_configured": self.client_id is not None,
            "access_token_configured": bool(self.access_token),
            "live_order_submission": False,
            "live_broker_order_submission": False,
        }

    def fingerprint(self) -> str:
        """Fingerprint non-secret configuration only."""
        payload = json.dumps(
            self.evidence(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


__all__ = ["UpstoxFeedConfig"]
