"""Configuration for the Upstox Market Data Feed V3 adapter."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class UpstoxFeedConfig:
    """Runtime configuration loaded from environment variables.

    No credentials are stored in source control.

    Reference:
        Upstox Market Data Feed V3 documentation.
    """

    access_token: str
    mode: str = "ltpc"
    timeout_seconds: float = 10.0

    # Reconnection policy for transient WebSocket failures.
    reconnect_max_attempts: int = 3
    reconnect_delay_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> "UpstoxFeedConfig":
        """Build configuration from environment variables."""
        access_token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()

        if not access_token:
            raise ValueError(
                "UPSTOX_ACCESS_TOKEN is required for the live market feed"
            )

        mode = os.getenv("UPSTOX_FEED_MODE", "ltpc").strip().lower()

        if mode not in {"ltpc", "full", "option_greeks", "full_d30"}:
            raise ValueError(f"Unsupported UPSTOX_FEED_MODE: {mode}")

        raw_timeout = os.getenv("UPSTOX_FEED_TIMEOUT_SECONDS", "10")

        try:
            timeout_seconds = float(raw_timeout)
        except ValueError as exc:
            raise ValueError(
                "UPSTOX_FEED_TIMEOUT_SECONDS must be numeric"
            ) from exc

        if timeout_seconds <= 0:
            raise ValueError("UPSTOX_FEED_TIMEOUT_SECONDS must be > 0")

        raw_attempts = os.getenv(
            "UPSTOX_RECONNECT_MAX_ATTEMPTS",
            "3",
        )

        try:
            reconnect_max_attempts = int(raw_attempts)
        except ValueError as exc:
            raise ValueError(
                "UPSTOX_RECONNECT_MAX_ATTEMPTS must be an integer"
            ) from exc

        if reconnect_max_attempts < 0:
            raise ValueError(
                "UPSTOX_RECONNECT_MAX_ATTEMPTS must be >= 0"
            )

        raw_delay = os.getenv(
            "UPSTOX_RECONNECT_DELAY_SECONDS",
            "1",
        )

        try:
            reconnect_delay_seconds = float(raw_delay)
        except ValueError as exc:
            raise ValueError(
                "UPSTOX_RECONNECT_DELAY_SECONDS must be numeric"
            ) from exc

        if reconnect_delay_seconds < 0:
            raise ValueError(
                "UPSTOX_RECONNECT_DELAY_SECONDS must be >= 0"
            )

        return cls(
            access_token=access_token,
            mode=mode,
            timeout_seconds=timeout_seconds,
            reconnect_max_attempts=reconnect_max_attempts,
            reconnect_delay_seconds=reconnect_delay_seconds,
        )
