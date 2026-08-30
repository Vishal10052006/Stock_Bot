"""Configuration for the Upstox Market Data Feed V3 adapter."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class UpstoxFeedConfig:
    """Runtime configuration loaded from environment variables.

    No credentials are stored in source control. ``access_token`` is supplied
    at runtime and can later be replaced by a token-refresh/authentication
    component without changing the feed interface.

    Reference:
        Upstox Market Data Feed V3 documentation.
    """

    access_token: str
    mode: str = "ltpc"
    timeout_seconds: float = 10.0

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

        return cls(
            access_token=access_token,
            mode=mode,
            timeout_seconds=timeout_seconds,
        )
