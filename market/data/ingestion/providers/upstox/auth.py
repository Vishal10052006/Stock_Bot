"""Upstox Market Data Feed V3 authorization boundary."""

from __future__ import annotations

import json

import requests

DEFAULT_AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"


class UpstoxAuthorizationError(RuntimeError):
    """Raised when Upstox cannot authorize a market-data connection."""


def get_authorized_websocket_uri(
    access_token: str,
    *,
    timeout_seconds: float = 10.0,
    authorize_url: str = DEFAULT_AUTHORIZE_URL,
) -> str:
    """Fetch the one-time authorized WebSocket URI for Market Data Feed V3.

    Reference:
        Upstox Market Data Feed Authorize V3 documentation.
    """
    token = access_token.strip()
    if not token:
        raise ValueError("access_token must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    try:
        response = requests.get(
            authorize_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "Stock-Bot/1.0",
            },
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise UpstoxAuthorizationError(
            "Failed to authorize the Upstox market-data WebSocket"
        ) from exc

    if not response.ok:
        raise UpstoxAuthorizationError(
            f"Upstox market-data authorization failed with HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise UpstoxAuthorizationError(
            "Upstox authorization response was not valid JSON"
        ) from exc

    try:
        data = payload["data"]
        uri = data.get("authorized_redirect_uri") or data.get("authorizedRedirectUri")
    except (TypeError, KeyError, AttributeError) as exc:
        raise UpstoxAuthorizationError(
            "Upstox authorization response did not contain an authorized redirect URI"
        ) from exc

    if not isinstance(uri, str) or not uri.startswith("wss://"):
        raise UpstoxAuthorizationError("Upstox returned an invalid WebSocket URI")

    return uri
