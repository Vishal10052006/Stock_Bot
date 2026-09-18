"""NSE security-wise daily historical data adapter."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Mapping

import requests

from market.data.historical.models import HistoricalDataRequest
from market.data.historical.nse_security import NSESecurityDailyBar


class NSESecurityDataError(RuntimeError):
    """Raised when NSE security-wise data cannot be retrieved or decoded."""


class NSESecurityWiseAdapter:
    """Fetch NSE security-wise daily price/volume records."""

    DEFAULT_BASE_URL = "https://www.nseindia.com"
    DEFAULT_REFERER = "https://www.nseindia.com/report-detail/eq_security"

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        base_url: str = DEFAULT_BASE_URL,
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if not base_url.strip():
            raise ValueError("base_url must not be empty")

        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()

    def get_daily_bars(
        self,
        request: HistoricalDataRequest,
    ) -> tuple[NSESecurityDailyBar, ...]:
        """Fetch daily NSE records for the request's date interval.

        The provider API treats both ``from`` and ``to`` as inclusive.
        The Stock Bot request contract remains ``[start, end)``.
        """

        if not isinstance(request, HistoricalDataRequest):
            raise TypeError(
                "request must be a HistoricalDataRequest"
            )

        if request.exchange.upper() != "NSE":
            raise ValueError(
                "NSE security-wise adapter only supports NSE"
            )

        if request.start is None or request.end is None:
            raise ValueError(
                "NSE security-wise requests require start and end"
            )

        if request.timeframe_minutes != 5:
            raise ValueError(
                "NSE security-wise daily data does not provide "
                "intraday candle timeframes"
            )

        start_date = request.start.date()
        end_date = request.end.date()

        # Stock Bot uses [start, end), while NSE's API uses
        # inclusive [from, to]. Translate the exclusive end explicitly.
        nse_end_date = end_date - timedelta(days=1)

        if start_date > nse_end_date:
            raise ValueError(
                "request date range must contain at least one calendar day"
            )

        self._establish_session()

        url = (
            f"{self._base_url}/api/historicalOR/"
            "generateSecurityWiseHistoricalData"
        )

        params = {
            "from": start_date.strftime("%d-%m-%Y"),
            "to": nse_end_date.strftime("%d-%m-%Y"),
            "symbol": request.symbol.strip().upper(),
            "type": "priceVolume",
            "series": "EQ",
        }

        try:
            response = self._session.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )

            response.raise_for_status()
        except Exception as exc:
            raise NSESecurityDataError(
                "NSE security-wise historical request failed"
            ) from exc

        try:
            payload = response.json()
        except Exception as exc:
            raise NSESecurityDataError(
                "NSE returned invalid JSON"
            ) from exc

        if not isinstance(payload, Mapping):
            raise ValueError(
                "NSE security-wise response must be a JSON object"
            )

        records = payload.get("data")

        if not isinstance(records, list):
            raise ValueError(
                "NSE security-wise response data must be a list"
            )

        bars = tuple(
            self._parse_record(record)
            for record in records
        )

        # Stock Bot's end boundary is exclusive.
        filtered = tuple(
            bar
            for bar in bars
            if start_date <= bar.session_date < request.end.date()
        )

        # NSE returns security-wise records newest-first. The Stock Bot
        # historical contract requires deterministic chronological order.
        return tuple(
            sorted(
                filtered,
                key=lambda bar: bar.session_date,
            )
        )

    def _establish_session(self) -> None:
        """Establish NSE cookies before requesting the API."""

        try:
            response = self._session.get(
                f"{self._base_url}/report-detail/eq_security",
                headers=self._headers(),
                timeout=self._timeout,
            )

            response.raise_for_status()
        except Exception as exc:
            raise NSESecurityDataError(
                "NSE session establishment failed"
            ) from exc

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": self.DEFAULT_REFERER,
        }

    @staticmethod
    def _parse_record(record: Any) -> NSESecurityDailyBar:
        """Parse one raw NSE API record without repairing it."""

        if not isinstance(record, Mapping):
            raise ValueError(
                "NSE security-wise record must be an object"
            )

        required = (
            "CH_SYMBOL",
            "CH_SERIES",
            "mTIMESTAMP",
            "CH_PREVIOUS_CLS_PRICE",
            "CH_OPENING_PRICE",
            "CH_TRADE_HIGH_PRICE",
            "CH_TRADE_LOW_PRICE",
            "CH_LAST_TRADED_PRICE",
            "CH_CLOSING_PRICE",
            "VWAP",
            "CH_TOT_TRADED_QTY",
            "CH_TOT_TRADED_VAL",
            "CH_TOTAL_TRADES",
        )

        missing = [
            field
            for field in required
            if field not in record
        ]

        if missing:
            raise ValueError(
                "NSE security-wise record is missing fields: "
                + ", ".join(missing)
            )

        try:
            session_date = datetime.strptime(
                str(record["mTIMESTAMP"]),
                "%d-%b-%Y",
            ).date()

            return NSESecurityDailyBar(
                symbol=str(record["CH_SYMBOL"]),
                series=str(record["CH_SERIES"]),
                session_date=session_date,
                previous_close=float(
                    record["CH_PREVIOUS_CLS_PRICE"]
                ),
                open=float(record["CH_OPENING_PRICE"]),
                high=float(record["CH_TRADE_HIGH_PRICE"]),
                low=float(record["CH_TRADE_LOW_PRICE"]),
                last_traded_price=float(
                    record["CH_LAST_TRADED_PRICE"]
                ),
                close=float(record["CH_CLOSING_PRICE"]),
                vwap=float(record["VWAP"]),
                traded_quantity=int(
                    record["CH_TOT_TRADED_QTY"]
                ),
                traded_value=float(
                    record["CH_TOT_TRADED_VAL"]
                ),
                total_trades=int(
                    record["CH_TOTAL_TRADES"]
                ),
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "invalid NSE security-wise record"
            ) from exc
