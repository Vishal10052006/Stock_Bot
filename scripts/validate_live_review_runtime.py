"""Read-only live validation for the personal V1 manual-review runtime.

This command performs one bounded observation cycle:
    Upstox WebSocket -> canonical MarketEvent
    Upstox REST GETs -> LiveManualRiskContext
    freshness/causality/system checks -> validation report

It never builds a BUY/SELL decision and never calls broker order APIs.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import Any

import pandas as pd

from market.data.events import MarketEvent
from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2
from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
from scripts.validate_live_review_env import (
    PreflightError,
    validate_live_review_environment,
)
from trading.live.risk_context import LiveManualRiskContext
from trading.live.upstox_risk_context import (
    LiveRiskContextUnavailable,
    UpstoxManualRiskContextProvider,
)


class LiveReviewValidationError(RuntimeError):
    """Raised when the read-only live validation cannot establish required state."""


@dataclass(frozen=True, slots=True)
class LiveReviewValidationReport:
    """Non-sensitive result of one live observation cycle."""

    status: str
    symbol: str
    market_event_received: bool
    market_event_valid: bool
    market_event_timestamp: str | None
    market_event_price_observed: bool
    account_context_observed: bool
    risk_context_fresh: bool
    risk_context_causal: bool
    market_data_valid: bool
    system_ready: bool
    kill_switch_active: bool
    broker_orders: int
    execution_authority: str
    blocked_reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_observations(
    *,
    symbol: str,
    event: MarketEvent | None,
    risk_context: LiveManualRiskContext | None,
    observed_at: pd.Timestamp,
) -> LiveReviewValidationReport:
    """Validate observed market/account state without producing a trade decision."""
    reasons: list[str] = []
    market_event_received = event is not None
    market_event_valid = event is not None
    event_timestamp = event.exchange_timestamp.isoformat() if event is not None else None

    if event is None:
        reasons.append("no valid live market event was observed")
    else:
        if event.symbol.strip().upper() != symbol.strip().upper():
            market_event_valid = False
            reasons.append("live market event symbol does not match requested symbol")
        if float(event.price) <= 0:
            market_event_valid = False
            reasons.append("live market event price is not positive")
        if pd.Timestamp(event.exchange_timestamp).tzinfo is None:
            market_event_valid = False
            reasons.append("live market event timestamp is not timezone-aware")

    risk_context_observed = risk_context is not None
    risk_context_fresh = False
    risk_context_causal = False
    market_data_valid = False
    system_ready = False
    kill_switch_active = False

    if risk_context is None:
        reasons.append("authoritative live account/risk context was not observed")
    else:
        validation_error = risk_context.validation_error(
            observed_at=observed_at,
            decision_timestamp=(
                pd.Timestamp(event.exchange_timestamp)
                if event is not None
                else observed_at
            ),
        )
        risk_context_causal = validation_error is None
        risk_context_fresh = validation_error is None
        if validation_error is not None:
            reasons.append(validation_error)

        market_data_valid = bool(risk_context.market_data_valid)
        system_ready = bool(risk_context.system_ready)
        kill_switch_active = bool(risk_context.kill_switch_active)

        if not market_data_valid:
            reasons.append("Upstox reports market data state is not valid for live review")
        if not system_ready:
            reasons.append("Upstox account/segment state is not ready")
        if kill_switch_active:
            reasons.append("Upstox kill switch is active")

    ready = (
        market_event_received
        and market_event_valid
        and risk_context_observed
        and risk_context_fresh
        and risk_context_causal
        and market_data_valid
        and system_ready
        and not kill_switch_active
    )

    return LiveReviewValidationReport(
        status="READY_FOR_HUMAN_REVIEW" if ready else "BLOCKED",
        symbol=symbol.strip().upper(),
        market_event_received=market_event_received,
        market_event_valid=market_event_valid,
        market_event_timestamp=event_timestamp,
        market_event_price_observed=bool(event is not None and float(event.price) > 0),
        account_context_observed=risk_context_observed,
        risk_context_fresh=risk_context_fresh,
        risk_context_causal=risk_context_causal,
        market_data_valid=market_data_valid,
        system_ready=system_ready,
        kill_switch_active=kill_switch_active,
        broker_orders=0,
        execution_authority="HUMAN_MANUAL_BUY_SELL",
        blocked_reasons=tuple(reasons),
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise LiveReviewValidationError(f"{name} is required")
    return value


def _positive_seconds(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise LiveReviewValidationError(f"{name} must be numeric") from exc
    if value <= 0:
        raise LiveReviewValidationError(f"{name} must be > 0")
    return value


def _wait_for_market_event(
    feed: UpstoxMarketFeed,
    symbol: str,
    *,
    max_wait_seconds: float,
) -> MarketEvent:
    """Read one event with a hard wall-clock bound."""
    result: list[MarketEvent] = []
    error: list[BaseException] = []
    done = Event()

    def consume() -> None:
        try:
            for event in feed.events():
                result.append(event)
                return
        except BaseException as exc:
            error.append(exc)
        finally:
            done.set()

    worker = Thread(target=consume, name="live-review-feed-observer", daemon=True)
    worker.start()

    if not done.wait(timeout=max_wait_seconds):
        feed.disconnect()
        done.wait(timeout=2.0)
        raise LiveReviewValidationError(
            f"no live market event observed for {symbol} within {max_wait_seconds:.1f}s"
        )

    if error:
        raise LiveReviewValidationError("live market feed observation failed") from error[0]
    if not result:
        raise LiveReviewValidationError("live market feed ended without an event")
    return result[0]


def run_live_review_validation(symbol: str) -> LiveReviewValidationReport:
    """Run one bounded read-only market + account observation cycle."""
    validate_live_review_environment()

    max_wait_seconds = _positive_seconds(
        "STOCK_BOT_LIVE_REVIEW_MAX_WAIT_SECONDS",
        15.0,
    )
    mapper = UpstoxInstrumentMapper.from_env()
    mapper.instrument_key(symbol)

    feed = UpstoxMarketFeed(
        UpstoxFeedConfig.from_env(),
        mapper,
        protobuf_module=MarketDataFeedV3_pb2,
    )

    try:
        feed.connect()
        feed.subscribe([symbol])
        event = _wait_for_market_event(
            feed,
            symbol,
            max_wait_seconds=max_wait_seconds,
        )
    finally:
        feed.disconnect()

    provider = UpstoxManualRiskContextProvider.from_env(
        day_state_path=Path(_required_env("STOCK_BOT_RISK_DAY_STATE_PATH")).expanduser(),
        api_base_url=_required_env("STOCK_BOT_RISK_API_BASE_URL"),
        exchange=_required_env("STOCK_BOT_RISK_EXCHANGE"),
        segment=_required_env("STOCK_BOT_RISK_SEGMENT"),
        timezone_name=_required_env("STOCK_BOT_RISK_TIMEZONE"),
        max_age_seconds=_positive_seconds(
            "STOCK_BOT_RISK_CONTEXT_MAX_AGE_SECONDS",
            30.0,
        ),
        source=_required_env("STOCK_BOT_RISK_CONTEXT_SOURCE"),
        timeout_seconds=_positive_seconds(
            "STOCK_BOT_RISK_CONTEXT_TIMEOUT_SECONDS",
            5.0,
        ),
        access_token_env=_required_env("STOCK_BOT_RISK_ACCESS_TOKEN_ENV"),
    )

    observed_at = pd.Timestamp.now(tz="UTC")
    try:
        risk_context = provider(pd.Timestamp(event.exchange_timestamp), symbol)
    except LiveRiskContextUnavailable:
        return validate_observations(
            symbol=symbol,
            event=event,
            risk_context=None,
            observed_at=observed_at,
        )

    observed_at = pd.Timestamp.now(tz="UTC")
    return validate_observations(
        symbol=symbol,
        event=event,
        risk_context=risk_context,
        observed_at=observed_at,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the personal V1 live-review market/account boundary without orders."
    )
    parser.add_argument("--symbol", default=None)
    args = parser.parse_args()

    symbol = (args.symbol or os.getenv("STOCK_BOT_LIVE_REVIEW_SYMBOL", "")).strip().upper()
    if not symbol:
        print(
            "[LIVE-REVIEW VALIDATION] BLOCKED: "
            "--symbol or STOCK_BOT_LIVE_REVIEW_SYMBOL is required"
        )
        return 2

    started = monotonic()
    try:
        report = run_live_review_validation(symbol)
    except (PreflightError, LiveReviewValidationError, LiveRiskContextUnavailable, ValueError) as exc:
        print(f"[LIVE-REVIEW VALIDATION] BLOCKED: {exc}")
        print("Broker orders      : 0")
        print("Execution authority: HUMAN_MANUAL_BUY_SELL")
        return 2

    print("[LIVE-REVIEW VALIDATION]")
    print(f"Status             : {report.status}")
    print(f"Symbol             : {report.symbol}")
    print(f"Market event       : {report.market_event_received and report.market_event_valid}")
    print(f"Account context    : {report.account_context_observed}")
    print(f"Risk fresh/causal  : {report.risk_context_fresh and report.risk_context_causal}")
    print(f"Market state valid : {report.market_data_valid}")
    print(f"System ready       : {report.system_ready}")
    print(f"Kill switch        : {report.kill_switch_active}")
    print(f"Broker orders      : {report.broker_orders}")
    print(f"Execution authority: {report.execution_authority}")
    print(f"Elapsed seconds    : {monotonic() - started:.2f}")

    for reason in report.blocked_reasons:
        print(f"Blocked reason     : {reason}")

    return 0 if report.status == "READY_FOR_HUMAN_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LiveReviewValidationError",
    "LiveReviewValidationReport",
    "run_live_review_validation",
    "validate_observations",
]
