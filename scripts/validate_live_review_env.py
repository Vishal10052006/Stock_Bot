"""Fail-closed local preflight for the personal V1 live-review runtime.

This command validates configuration shape only. It does not contact Upstox,
fetch account state, place orders, or claim that the runtime is ready to trade.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class PreflightError(ValueError):
    """Raised when required live-review configuration is invalid."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise PreflightError(f"{name} is required")
    return value


def _positive_float(name: str) -> float:
    raw = _required(name)
    try:
        value = float(raw)
    except ValueError as exc:
        raise PreflightError(f"{name} must be numeric") from exc
    if value <= 0:
        raise PreflightError(f"{name} must be > 0")
    return value


def _json_object(name: str, *, required: bool = True) -> dict:
    raw = os.getenv(name, "").strip()
    if not raw:
        if required:
            raise PreflightError(f"{name} is required")
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PreflightError(f"{name} must contain valid JSON") from exc
    if not isinstance(value, dict) or not value:
        raise PreflightError(f"{name} must decode to a non-empty JSON object")
    return value


def validate_live_review_environment() -> dict[str, object]:
    """Validate local configuration without making any network calls."""
    _required("UPSTOX_ACCESS_TOKEN")
    _required("UPSTOX_INSTRUMENT_MAP")
    _json_object("UPSTOX_INSTRUMENT_MAP")
    _json_object("UPSTOX_CONTEXT_INSTRUMENT_MAP", required=False)

    _positive_float("STOCK_BOT_RISK_CONTEXT_MAX_AGE_SECONDS")
    _positive_float("STOCK_BOT_RISK_CONTEXT_TIMEOUT_SECONDS")
    _required("STOCK_BOT_RISK_DAY_STATE_PATH")
    _required("STOCK_BOT_RISK_API_BASE_URL")
    _required("STOCK_BOT_RISK_EXCHANGE")
    _required("STOCK_BOT_RISK_SEGMENT")
    _required("STOCK_BOT_RISK_TIMEZONE")
    _required("STOCK_BOT_RISK_CONTEXT_SOURCE")

    access_token_env = _required("STOCK_BOT_RISK_ACCESS_TOKEN_ENV")
    if not access_token_env.isidentifier():
        raise PreflightError(
            "STOCK_BOT_RISK_ACCESS_TOKEN_ENV must be a valid environment variable name"
        )
    if not os.getenv(access_token_env, "").strip():
        raise PreflightError(
            f"{access_token_env} (named by STOCK_BOT_RISK_ACCESS_TOKEN_ENV) is required"
        )

    day_state = Path(os.environ["STOCK_BOT_RISK_DAY_STATE_PATH"]).expanduser()
    parent = day_state.parent
    if not parent.exists():
        raise PreflightError(
            f"risk day-state parent directory does not exist: {parent}"
        )

    return {
        "market_feed": "configured",
        "risk_account_observer": "configured",
        "network_calls": False,
        "broker_orders": False,
        "execution_authority": "HUMAN_MANUAL_BUY_SELL",
    }


def main() -> int:
    try:
        result = validate_live_review_environment()
    except PreflightError as exc:
        print(f"[LIVE-REVIEW PREFLIGHT] BLOCKED: {exc}")
        return 2

    print("[LIVE-REVIEW PREFLIGHT] CONFIGURATION OK")
    print(f"Network calls       : {result['network_calls']}")
    print(f"Broker orders       : {result['broker_orders']}")
    print(f"Execution authority : {result['execution_authority']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["PreflightError", "validate_live_review_environment"]
