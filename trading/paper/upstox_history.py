"""Causal Upstox V3 historical-candle provider for live paper startup.

The provider uses the same Upstox access token as the realtime feed and
returns only candles strictly before a requested decision timestamp for seed
history. Live candles still come exclusively from the realtime feed.
"""

from __future__ import annotations

from datetime import timedelta
import os
import time
from urllib.parse import quote
import requests

import pandas as pd

from market.candles.models import Candle


class UpstoxHistoryProvider:
    """Fetch causal 5-minute history from Upstox Historical Candle V3."""

    def __init__(
        self,
        *,
        access_token: str,
        instrument_mapper,
        lookback_days: int = 10,
        interval_minutes: int = 5,
    ) -> None:
        if not access_token.strip():
            raise ValueError("access_token must not be empty")
        if lookback_days <= 0:
            raise ValueError("lookback_days must be positive")
        if interval_minutes <= 0 or interval_minutes > 300:
            raise ValueError("interval_minutes must be in [1, 300]")
        self.access_token = access_token.strip()
        self.instrument_mapper = instrument_mapper
        self.lookback_days = lookback_days
        self.interval_minutes = interval_minutes

    @classmethod
    def from_env(cls, instrument_mapper, *, env_var: str = "UPSTOX_ACCESS_TOKEN"):
        """Create a history provider from the existing Upstox credentials."""
        token = os.getenv(env_var, "").strip()
        if not token:
            raise ValueError(f"{env_var} is required for Upstox historical data")
        return cls(
            access_token=token,
            instrument_mapper=instrument_mapper,
            lookback_days=int(os.getenv("UPSTOX_HISTORY_LOOKBACK_DAYS", "10")),
        )

    def _fetch(self, instrument_key: str, cutoff: pd.Timestamp) -> list[list]:
        """Fetch raw V3 candles for one instrument."""
        local = cutoff.tz_convert("Asia/Kolkata")
        to_date = local.date().isoformat()
        from_date = (local.date() - timedelta(days=self.lookback_days)).isoformat()
        encoded_key = quote(instrument_key, safe="")
        url = (
            "https://api.upstox.com/v3/historical-candle/"
            f"{encoded_key}/minutes/{self.interval_minutes}/{to_date}/{from_date}"
        )
        response = requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            raise RuntimeError("Upstox historical candle request was unsuccessful")
        return body.get("data", {}).get("candles", [])

    def frame(
        self,
        symbol: str,
        cutoff: pd.Timestamp,
        *,
        include_cutoff: bool = False,
    ) -> pd.DataFrame:
        """Return causal OHLCV history with an optional inclusive cutoff."""
        timestamp = pd.Timestamp(cutoff)
        if timestamp.tzinfo is None:
            raise ValueError("cutoff must be timezone-aware")

        normalized = symbol.strip().upper()
        instrument_key = self.instrument_mapper.instrument_key(normalized)
        candles = self._fetch(instrument_key, timestamp)

        rows = []
        for raw in candles:
            if len(raw) < 6:
                continue
            rows.append(
                {
                    "timestamp": pd.Timestamp(raw[0]),
                    "symbol": normalized,
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": float(raw[5]),
                }
            )

        frame = pd.DataFrame(
            rows,
            columns=[
                "timestamp",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )
        if frame.empty:
            return frame

        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"],
            utc=True,
            errors="raise",
        )
        if include_cutoff:
            frame = frame.loc[frame["timestamp"] <= timestamp].copy()
        else:
            frame = frame.loc[frame["timestamp"] < timestamp].copy()
        frame = frame.sort_values("timestamp", kind="stable")
        frame = frame.drop_duplicates(["timestamp", "symbol"], keep="last")
        return frame.reset_index(drop=True)

    def _fetch_intraday(self, instrument_key: str) -> list[list]:
        """Fetch raw current-trading-day candles from Upstox Intraday V3."""
        encoded_key = quote(instrument_key, safe="")
        url = (
            "https://api.upstox.com/v3/historical-candle/intraday/"
            f"{encoded_key}/minutes/{self.interval_minutes}"
        )
        response = requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            raise RuntimeError("Upstox intraday candle request was unsuccessful")
        return body.get("data", {}).get("candles", [])

    @staticmethod
    def _frame_from_raw(symbol: str, candles: list[list]) -> pd.DataFrame:
        """Normalize raw Upstox candles into the canonical OHLCV frame."""
        rows = []
        for raw in candles:
            if len(raw) < 6:
                continue
            rows.append(
                {
                    "timestamp": pd.Timestamp(raw[0]),
                    "symbol": symbol,
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": float(raw[5]),
                }
            )

        frame = pd.DataFrame(
            rows,
            columns=[
                "timestamp",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )
        if frame.empty:
            return frame

        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"],
            utc=True,
            errors="raise",
        )
        frame = frame.sort_values("timestamp", kind="stable")
        frame = frame.drop_duplicates(["timestamp", "symbol"], keep="last")
        return frame.reset_index(drop=True)

    def intraday_frame(
        self,
        symbol: str,
        *,
        target_timestamp: pd.Timestamp | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> pd.DataFrame:
        """Return current-day candles, retrying until an optional target appears."""
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")
        if retry_delay < 0:
            raise ValueError("retry_delay must not be negative")

        normalized = symbol.strip().upper()
        instrument_key = self.instrument_mapper.instrument_key(normalized)

        target_utc = None
        if target_timestamp is not None:
            target = pd.Timestamp(target_timestamp)
            if target.tzinfo is None:
                raise ValueError("target_timestamp must be timezone-aware")
            target_utc = target.tz_convert("UTC")

        attempts = max_retries if target_utc is not None else 1
        frame = pd.DataFrame()

        for attempt in range(attempts):
            frame = self._frame_from_raw(
                normalized,
                self._fetch_intraday(instrument_key),
            )
            if target_utc is None:
                break
            if not frame.empty and (frame["timestamp"] == target_utc).any():
                break
            if attempt + 1 < attempts and retry_delay:
                time.sleep(retry_delay)

        if target_utc is not None and not frame.empty:
            frame = frame.loc[frame["timestamp"] <= target_utc].copy()
            frame = frame.reset_index(drop=True)

        return frame

    def candles(self, symbol: str, cutoff: pd.Timestamp) -> tuple[Candle, ...]:
        """Return causal Candle objects for canonical history seeding."""
        frame = self.frame(symbol, cutoff)
        return tuple(
            Candle(
                symbol=row.symbol,
                exchange="NSE",
                timeframe_minutes=self.interval_minutes,
                timestamp=row.timestamp,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            for row in frame.itertuples(index=False)
        )


__all__ = ["UpstoxHistoryProvider"]
