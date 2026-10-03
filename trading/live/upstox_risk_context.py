"""Read-only Upstox account observer for V1 manual Risk.

This module performs GET-only account observations. It has no order, modify,
cancel, exit, or other state-changing broker operation.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from trading.live.risk_context import LiveManualRiskContext
from trading.risk.kill_switch import KillSwitchState


class LiveRiskContextUnavailable(RuntimeError):
    """Raised when authoritative live account state cannot be established."""


@dataclass(frozen=True, slots=True)
class LiveDayRiskState:
    """Persisted observed day-start and peak risk-capital state."""

    trading_date: str
    day_start_equity: float
    peak_equity: float

    def __post_init__(self) -> None:
        if not self.trading_date.strip():
            raise ValueError("trading_date must not be empty")
        for name, value in (
            ("day_start_equity", self.day_start_equity),
            ("peak_equity", self.peak_equity),
        ):
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")


class LiveDayRiskStateStore:
    """Durable store for observed day-start/peak state; never stores credentials."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not str(self.path):
            raise ValueError("state path must be supplied")

    def load(self, trading_date: str) -> LiveDayRiskState | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LiveRiskContextUnavailable(
                "live day-risk state store cannot be read"
            ) from exc
        if not isinstance(raw, Mapping):
            raise LiveRiskContextUnavailable("live day-risk state must be a JSON object")
        if str(raw.get("trading_date", "")) != trading_date:
            return None
        return LiveDayRiskState(
            trading_date=trading_date,
            day_start_equity=float(raw["day_start_equity"]),
            peak_equity=float(raw["peak_equity"]),
        )

    def save(self, state: LiveDayRiskState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trading_date": state.trading_date,
            "day_start_equity": state.day_start_equity,
            "peak_equity": state.peak_equity,
        }
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise LiveRiskContextUnavailable(
                "live day-risk state store cannot be written"
            ) from exc


class UpstoxReadOnlyAccountClient:
    """GET-only transport for the Upstox account/portfolio APIs used by Risk."""

    def __init__(
        self,
        access_token: str,
        *,
        api_base_url: str,
        timeout_seconds: float,
    ) -> None:
        if not access_token.strip():
            raise ValueError("access_token must not be empty")
        if not api_base_url.strip():
            raise ValueError("api_base_url must not be empty")
        if not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self._access_token = access_token
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = float(timeout_seconds)

    def get(self, path: str, *, headers: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        if not path.startswith("/"):
            raise ValueError("API path must start with '/'")
        request_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }
        if headers:
            request_headers.update(headers)

        request = Request(
            self._api_base_url + path,
            method="GET",
            headers=request_headers,
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise LiveRiskContextUnavailable(
                f"Upstox read-only API HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise LiveRiskContextUnavailable(
                "Upstox read-only API transport failure"
            ) from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LiveRiskContextUnavailable(
                "Upstox read-only API returned non-JSON data"
            ) from exc
        if not isinstance(decoded, Mapping):
            raise LiveRiskContextUnavailable(
                "Upstox read-only API response must be an object"
            )
        if decoded.get("status") not in {"success", None}:
            raise LiveRiskContextUnavailable(
                f"Upstox read-only API returned status {decoded.get('status')!r}"
            )
        return decoded

    @staticmethod
    def data(response: Mapping[str, Any]) -> Any:
        data = response.get("data")
        if data is None:
            raise LiveRiskContextUnavailable("Upstox response is missing data")
        return data


@dataclass(frozen=True, slots=True)
class UpstoxManualRiskContextProvider:
    """Build a complete V1 Risk snapshot from current Upstox read-only truth."""

    client: UpstoxReadOnlyAccountClient
    day_state: LiveDayRiskStateStore
    exchange: str
    segment: str
    timezone_name: str
    max_age_seconds: float
    source: str

    def __post_init__(self) -> None:
        if not self.exchange.strip():
            raise ValueError("exchange must not be empty")
        if not self.segment.strip():
            raise ValueError("segment must not be empty")
        if not self.timezone_name.strip():
            raise ValueError("timezone_name must not be empty")
        if not math.isfinite(float(self.max_age_seconds)) or self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive and finite")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        ZoneInfo(self.timezone_name)

    @classmethod
    def from_env(
        cls,
        *,
        day_state_path: Path,
        api_base_url: str,
        exchange: str,
        segment: str,
        timezone_name: str,
        max_age_seconds: float,
        source: str,
        timeout_seconds: float,
        access_token_env: str,
    ) -> "UpstoxManualRiskContextProvider":
        token = os.getenv(access_token_env, "").strip()
        if not token:
            raise LiveRiskContextUnavailable(
                f"{access_token_env} must be set for live account observation"
            )
        return cls(
            client=UpstoxReadOnlyAccountClient(
                token,
                api_base_url=api_base_url,
                timeout_seconds=timeout_seconds,
            ),
            day_state=LiveDayRiskStateStore(day_state_path),
            exchange=exchange,
            segment=segment,
            timezone_name=timezone_name,
            max_age_seconds=max_age_seconds,
            source=source,
        )

    def __call__(
        self,
        decision_timestamp: pd.Timestamp,
        symbol: str,
    ) -> LiveManualRiskContext:
        observed_at = pd.Timestamp.now(tz="UTC")
        funds = self._funds()
        positions = self._positions()
        holdings = self._holdings()
        trades = self._trades()
        profile = self._profile()
        kill = self._kill_switch()
        market = self._market_status()

        available_equity = self._positive_number(
            funds["available_to_trade"]["total"],
            "available_to_trade.total",
        )
        available_cash = self._nonnegative_number(
            funds["available_to_trade"]["cash_available_to_trade"]["total"],
            "cash_available_to_trade.total",
        )

        account_date = observed_at.tz_convert(
            ZoneInfo(self.timezone_name)
        ).date().isoformat()
        trade_count = len(trades)

        day_state = self.day_state.load(account_date)
        if day_state is None:
            if trade_count != 0:
                raise LiveRiskContextUnavailable(
                    "day-start risk state is missing after today's broker trades; "
                    "refusing to reconstruct it from current state"
                )
            day_state = LiveDayRiskState(
                trading_date=account_date,
                day_start_equity=available_equity,
                peak_equity=available_equity,
            )
        elif day_state.trading_date != account_date:
            raise LiveRiskContextUnavailable(
                "persisted day-risk state date does not match the current trading date"
            )

        peak_equity = max(day_state.peak_equity, available_equity)
        if peak_equity != day_state.peak_equity:
            day_state = LiveDayRiskState(
                trading_date=day_state.trading_date,
                day_start_equity=day_state.day_start_equity,
                peak_equity=peak_equity,
            )
        self.day_state.save(day_state)

        position_rows = tuple(self._sequence(positions, "positions"))
        holding_rows = tuple(self._sequence(holdings, "holdings"))

        position_state = self._position_state(position_rows, holding_rows, symbol)
        realized_pnl = sum(
            self._number(row.get("realised", 0.0), "position.realised")
            for row in position_rows
        )
        unrealized_pnl = sum(
            self._number(row.get("unrealised", 0.0), "position.unrealised")
            for row in position_rows
        ) + sum(
            self._number(row.get("day_change", 0.0), "holding.day_change")
            for row in holding_rows
        )

        symbol_exposure = self._exposure_by_symbol(position_rows, holding_rows)
        gross_exposure = sum(symbol_exposure.values())

        kill_active, kill_state = self._kill_state(kill, self.segment)
        segment_active = self._segment_active(kill, self.segment)
        profile_active = bool(profile.get("is_active", False))
        market_open = str(market.get("status", "")).strip().upper() in {
            "NORMAL_OPEN",
            "NORMAL_CLOSE",
            "PRE_OPEN",
            "PRE_OPEN_START",
            "PRE_OPEN_END",
        }

        return LiveManualRiskContext(
            as_of=observed_at,
            source=self.source,
            available_equity=available_equity,
            day_start_equity=day_state.day_start_equity,
            available_cash=available_cash,
            peak_equity=peak_equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            open_positions=position_state["open_positions"],
            trades_today=trade_count,
            gross_exposure=gross_exposure,
            symbol_already_open=position_state["symbol_already_open"],
            position_context=None,
            liquidity_available=available_equity > 0,
            kill_switch_active=kill_active,
            sector=None,
            symbol_exposure=symbol_exposure,
            sector_exposure={},
            pairwise_correlation={},
            atr=None,
            high_volatility=False,
            market_data_valid=market_open,
            system_ready=profile_active and segment_active,
            kill_switch_state=kill_state,
            max_age_seconds=self.max_age_seconds,
        )

    def _funds(self) -> Mapping[str, Any]:
        return self.client.data(
            self.client.get(
                "/v3/user/get-funds-and-margin",
                headers={"Api-Version": "3.0"},
            )
        )

    def _positions(self) -> Any:
        return self.client.data(
            self.client.get("/v2/portfolio/short-term-positions")
        )

    def _holdings(self) -> Any:
        return self.client.data(
            self.client.get("/v2/portfolio/long-term-holdings")
        )

    def _trades(self) -> Any:
        return self.client.data(
            self.client.get("/v2/order/trades/get-trades-for-day")
        )

    def _profile(self) -> Mapping[str, Any]:
        data = self.client.data(self.client.get("/v2/user/profile"))
        if not isinstance(data, Mapping):
            raise LiveRiskContextUnavailable("Upstox profile data must be an object")
        return data

    def _kill_switch(self) -> Any:
        return self.client.data(self.client.get("/v2/user/kill-switch"))

    def _market_status(self) -> Mapping[str, Any]:
        data = self.client.data(
            self.client.get(f"/v2/market/status/{quote(self.exchange, safe='')}")
        )
        if not isinstance(data, Mapping):
            raise LiveRiskContextUnavailable("Upstox market status data must be an object")
        return data

    @staticmethod
    def _sequence(value: Any, name: str) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(value, list):
            raise LiveRiskContextUnavailable(f"Upstox {name} data must be a list")
        rows = []
        for row in value:
            if not isinstance(row, Mapping):
                raise LiveRiskContextUnavailable(
                    f"Upstox {name} entry must be an object"
                )
            rows.append(row)
        return tuple(rows)

    @staticmethod
    def _number(value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise LiveRiskContextUnavailable(
                f"{field_name} must be numeric"
            ) from exc
        if not math.isfinite(number):
            raise LiveRiskContextUnavailable(f"{field_name} must be finite")
        return number

    @classmethod
    def _positive_number(cls, value: Any, field_name: str) -> float:
        number = cls._number(value, field_name)
        if number <= 0:
            raise LiveRiskContextUnavailable(f"{field_name} must be positive")
        return number

    @classmethod
    def _nonnegative_number(cls, value: Any, field_name: str) -> float:
        number = cls._number(value, field_name)
        if number < 0:
            raise LiveRiskContextUnavailable(f"{field_name} must be non-negative")
        return number

    @staticmethod
    def _symbol_matches(candidate: str, symbol: str) -> bool:
        left = candidate.strip().upper()
        right = symbol.strip().upper()
        return left == right or left.split("-")[0] == right.split("-")[0]

    @classmethod
    def _position_state(
        cls,
        positions: tuple[Mapping[str, Any], ...],
        holdings: tuple[Mapping[str, Any], ...],
        symbol: str,
    ) -> dict[str, Any]:
        open_positions = 0
        symbol_already_open = False
        seen_symbols: set[str] = set()

        for row in positions:
            quantity = cls._number(row.get("quantity", 0), "position.quantity")
            candidate = str(row.get("trading_symbol") or row.get("tradingsymbol") or "")
            if quantity != 0 and candidate:
                open_positions += 1
                normalized = candidate.split("-")[0].upper()
                seen_symbols.add(normalized)
                symbol_already_open |= cls._symbol_matches(candidate, symbol)

        for row in holdings:
            quantity = cls._number(row.get("quantity", 0), "holding.quantity")
            candidate = str(row.get("trading_symbol") or row.get("tradingsymbol") or "")
            if quantity != 0 and candidate:
                normalized = candidate.split("-")[0].upper()
                seen_symbols.add(normalized)
                symbol_already_open |= cls._symbol_matches(candidate, symbol)

        return {
            "open_positions": open_positions,
            "symbol_already_open": symbol_already_open,
            "symbols": seen_symbols,
        }

    @classmethod
    def _exposure_by_symbol(
        cls,
        positions: tuple[Mapping[str, Any], ...],
        holdings: tuple[Mapping[str, Any], ...],
    ) -> dict[str, float]:
        exposure: dict[str, float] = {}

        for row in positions:
            symbol = str(row.get("trading_symbol") or row.get("tradingsymbol") or "").strip()
            quantity = cls._number(row.get("quantity", 0), "position.quantity")
            value = abs(cls._number(row.get("value", 0), "position.value"))
            if symbol and quantity != 0:
                key = symbol.split("-")[0].upper()
                exposure[key] = exposure.get(key, 0.0) + value

        for row in holdings:
            symbol = str(row.get("trading_symbol") or row.get("tradingsymbol") or "").strip()
            quantity = cls._number(row.get("quantity", 0), "holding.quantity")
            last_price = cls._number(row.get("last_price", 0), "holding.last_price")
            if symbol and quantity != 0:
                key = symbol.split("-")[0].upper()
                exposure[key] = exposure.get(key, 0.0) + abs(quantity * last_price)

        return exposure

    @staticmethod
    def _kill_state(
        data: Any,
        segment: str,
    ) -> tuple[bool, KillSwitchState]:
        if not isinstance(data, list):
            raise LiveRiskContextUnavailable("Upstox kill-switch data must be a list")
        matches = [
            row for row in data
            if isinstance(row, Mapping)
            and str(row.get("segment", "")).strip().upper() == segment.strip().upper()
        ]
        if len(matches) != 1:
            raise LiveRiskContextUnavailable(
                f"Upstox kill-switch response must contain exactly one {segment} entry"
            )
        row = matches[0]
        enabled = row.get("kill_switch_enabled")
        if not isinstance(enabled, bool):
            raise LiveRiskContextUnavailable(
                "Upstox kill-switch state must be boolean"
            )
        return enabled, KillSwitchState(manual=enabled)

    @staticmethod
    def _segment_active(data: Any, segment: str) -> bool:
        if not isinstance(data, list):
            raise LiveRiskContextUnavailable("Upstox kill-switch data must be a list")
        matches = [
            row for row in data
            if isinstance(row, Mapping)
            and str(row.get("segment", "")).strip().upper() == segment.strip().upper()
        ]
        if len(matches) != 1:
            raise LiveRiskContextUnavailable(
                f"Upstox kill-switch response must contain exactly one {segment} entry"
            )
        return str(matches[0].get("segment_status", "")).strip().upper() == "ACTIVE"


__all__ = [
    "LiveDayRiskState",
    "LiveDayRiskStateStore",
    "LiveRiskContextUnavailable",
    "UpstoxManualRiskContextProvider",
    "UpstoxReadOnlyAccountClient",
]
