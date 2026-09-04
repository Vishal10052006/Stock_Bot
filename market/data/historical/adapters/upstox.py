"""Upstox V3 historical-candle adapter."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from math import isfinite
from typing import Any
from urllib.parse import quote

import requests

from market.candles.models import Candle
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.providers import (
    HistoricalMarketDataProvider,
    HistoricalProviderRole,
)
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)


DEFAULT_HISTORICAL_URL = (
    "https://api.upstox.com/v3/historical-candle"
)


class UpstoxHistoricalDataError(RuntimeError):
    """Raised when Upstox historical data cannot be retrieved or decoded."""


class UpstoxHistoricalMarketDataProvider(
    HistoricalMarketDataProvider
):
    """Retrieve canonical NSE historical candles from Upstox V3."""

    role = HistoricalProviderRole.CANONICAL

    def __init__(
        self,
        access_token: str,
        instrument_mapper: UpstoxInstrumentMapper,
        *,
        timeout_seconds: float = 10.0,
        base_url: str = DEFAULT_HISTORICAL_URL,
        session: Any = requests,
    ) -> None:
        token = access_token.strip()

        if not token:
            raise ValueError("access_token must not be empty")

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero"
            )

        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty string")

        self.access_token = token
        self.instrument_mapper = instrument_mapper
        self.timeout_seconds = float(timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self._session = session

    @staticmethod
    def _validate_request(
        request: HistoricalDataRequest,
    ) -> None:
        if not isinstance(request, HistoricalDataRequest):
            raise TypeError(
                "request must be a HistoricalDataRequest"
            )

        if request.exchange.upper() != "NSE":
            raise ValueError(
                "Upstox historical adapter currently supports NSE only"
            )

        if request.timeframe_minutes <= 0:
            raise ValueError(
                "timeframe_minutes must be positive"
            )

        if request.timeframe_minutes > 300:
            raise ValueError(
                "Upstox minute historical interval must be <= 300"
            )

    @staticmethod
    def _iter_date_chunks(
        request: HistoricalDataRequest,
    ):
        """Yield historical request windows of at most 30 calendar days."""
        if request.start is None or request.end is None:
            raise ValueError(
                "Upstox historical requests require start and end timestamps"
            )

        current = request.start

        while current < request.end:
            chunk_end_date = min(
                current.date() + timedelta(days=29),
                request.end.date(),
            )

            if chunk_end_date == request.end.date():
                chunk_end = request.end
            else:
                chunk_end = datetime.combine(
                    chunk_end_date,
                    datetime.max.time().replace(microsecond=0),
                    tzinfo=current.tzinfo,
                )

            yield current, chunk_end

            current = datetime.combine(
                chunk_end_date + timedelta(days=1),
                datetime.min.time(),
                tzinfo=current.tzinfo,
            )

    @staticmethod
    def _date_string(timestamp: datetime) -> str:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("historical request timestamps must be timezone-aware")

        return timestamp.date().isoformat()

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if not isinstance(value, str):
            raise UpstoxHistoricalDataError(
                "Upstox candle timestamp must be a string"
            )

        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError as exc:
            raise UpstoxHistoricalDataError(
                "Upstox returned an invalid candle timestamp"
            ) from exc

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise UpstoxHistoricalDataError(
                "Upstox returned a timezone-naive candle timestamp"
            )

        return timestamp

    @staticmethod
    def _parse_candle(
        raw: Any,
        *,
        request: HistoricalDataRequest,
    ) -> Candle:
        if not isinstance(raw, (list, tuple)) or len(raw) < 6:
            raise UpstoxHistoricalDataError(
                "Upstox returned a malformed candle"
            )

        timestamp = UpstoxHistoricalMarketDataProvider._parse_timestamp(
            raw[0]
        )

        try:
            values = {
                "open": float(raw[1]),
                "high": float(raw[2]),
                "low": float(raw[3]),
                "close": float(raw[4]),
                "volume": float(raw[5]),
            }
        except (TypeError, ValueError, OverflowError) as exc:
            raise UpstoxHistoricalDataError(
                "Upstox returned non-numeric OHLCV data"
            ) from exc

        if any(not isfinite(value) for value in values.values()):
            raise UpstoxHistoricalDataError(
                "Upstox returned non-finite OHLCV data"
            )

        if values["open"] <= 0:
            raise UpstoxHistoricalDataError(
                "Upstox returned a non-positive open price"
            )

        if values["high"] <= 0:
            raise UpstoxHistoricalDataError(
                "Upstox returned a non-positive high price"
            )

        if values["low"] <= 0:
            raise UpstoxHistoricalDataError(
                "Upstox returned a non-positive low price"
            )

        if values["close"] <= 0:
            raise UpstoxHistoricalDataError(
                "Upstox returned a non-positive close price"
            )

        if values["volume"] < 0:
            raise UpstoxHistoricalDataError(
                "Upstox returned a negative volume"
            )

        try:
            return Candle(
                symbol=request.symbol,
                exchange=request.exchange,
                timeframe_minutes=request.timeframe_minutes,
                timestamp=timestamp,
                **values,
            )
        except (TypeError, ValueError) as exc:
            raise UpstoxHistoricalDataError(
                "Upstox returned an invalid canonical candle"
            ) from exc

    def get_bars(
        self,
        request: HistoricalDataRequest,
    ) -> Sequence[Candle]:
        """Fetch and normalize historical candles from Upstox V3."""

        self._validate_request(request)

        instrument_key = self.instrument_mapper.instrument_key(
            request.symbol
        )

        encoded_instrument = quote(
            instrument_key,
            safe="",
        )

        if request.start is None and request.end is None:
            raise ValueError(
                "Upstox historical requests require start and end timestamps"
            )

        if request.start is None:
            raise ValueError(
                "Upstox historical requests require a start timestamp"
            )

        if request.end is None:
            raise ValueError(
                "Upstox historical requests require an end timestamp"
            )

        if request.end <= request.start:
            raise ValueError(
                "request end must be after request start"
            )

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        all_bars: list[Candle] = []

        for chunk_start, chunk_end in self._iter_date_chunks(request):
            from_date = self._date_string(chunk_start)
            to_date = self._date_string(chunk_end)

            url = (
                f"{self.base_url}/"
                f"{encoded_instrument}/minutes/"
                f"{request.timeframe_minutes}/"
                f"{to_date}/"
                f"{from_date}"
            )

            try:
                response = self._session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise UpstoxHistoricalDataError(
                    "Upstox historical request failed"
                ) from exc

            if not response.ok:
                raise UpstoxHistoricalDataError(
                    "Upstox historical request failed with "
                    f"HTTP {response.status_code}"
                )

            try:
                payload = response.json()
            except (ValueError, TypeError) as exc:
                raise UpstoxHistoricalDataError(
                    "Upstox historical response was not valid JSON"
                ) from exc

            if not isinstance(payload, dict):
                raise UpstoxHistoricalDataError(
                    "Upstox historical response must be a JSON object"
                )

            if payload.get("status") != "success":
                raise UpstoxHistoricalDataError(
                    "Upstox historical response did not report success"
                )

            try:
                candles = payload["data"]["candles"]
            except (KeyError, TypeError) as exc:
                raise UpstoxHistoricalDataError(
                    "Upstox historical response did not contain candles"
                ) from exc

            if not isinstance(candles, list):
                raise UpstoxHistoricalDataError(
                    "Upstox historical candles must be a list"
                )

            all_bars.extend(
                self._parse_candle(
                    raw,
                    request=request,
                )
                for raw in candles
            )

        if not all_bars:
            raise UpstoxHistoricalDataError(
                "Upstox returned no historical candles"
            )

        sorted_bars = sorted(
            all_bars,
            key=lambda bar: bar.timestamp,
        )

        if request.start is not None:
            sorted_bars = [
                bar
                for bar in sorted_bars
                if bar.timestamp >= request.start
            ]

        if request.end is not None:
            sorted_bars = [
                bar
                for bar in sorted_bars
                if bar.timestamp < request.end
            ]

        return tuple(sorted_bars)
