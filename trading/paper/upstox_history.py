"""Causal Upstox V3 historical-candle provider for live paper startup.

The provider uses the same Upstox access token as the realtime feed and
supports two explicit causal views:

* strict history for seed data: timestamps < decision time
* inclusive history for point-in-time benchmark context: timestamps <= decision time

Live candles still come exclusively from the realtime feed.
"""

from __future__ import annotations

from datetime import timedelta
import json
import os
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

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
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
        )
        with urlopen(request, timeout=15) as response:
            payload = response.read().decode("utf-8")
        body = json.loads(payload)
        if body.get("status") != "success":
            raise RuntimeError("Upstox historical candle request was unsuccessful")
        return body.get("data", {}).get("candles", [])

    def _frame(self, symbol: str, cutoff: pd.Timestamp, *, inclusive: bool) -> pd.DataFrame:
        """Normalize raw candles and apply the requested causal cutoff."""
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

        if inclusive:
            frame = frame.loc[frame["timestamp"] <= timestamp].copy()
        else:
            frame = frame.loc[frame["timestamp"] < timestamp].copy()

        frame = frame.sort_values("timestamp", kind="stable")
        frame = frame.drop_duplicates(["timestamp", "symbol"], keep="last")
        return frame.reset_index(drop=True)

    def frame(self, symbol: str, cutoff: pd.Timestamp) -> pd.DataFrame:
        """Return causal OHLCV history strictly before the decision time.

        This remains the default view for seed history so a live decision
        candle is never duplicated into its own historical feature window.
        """
        return self._frame(symbol, cutoff, inclusive=False)

    def frame_through(self, symbol: str, cutoff: pd.Timestamp) -> pd.DataFrame:
        """Return point-in-time OHLCV history through the decision timestamp.

        This view is intended for benchmark/MarketContext providers whose
        contract requires the latest available observation to equal the
        decision timestamp. It remains causal because it admits no row
        strictly after the cutoff.
        """
        return self._frame(symbol, cutoff, inclusive=True)

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
