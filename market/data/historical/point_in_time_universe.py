"""Point-in-time historical universe construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import gzip
import json

from market.data.historical.adapters.nse_bhavcopy import (
    NSEBhavcopyAdapter,
)
from market.data.historical.adapters.nse_security_master import (
    NSESecurityMasterAdapter,
)
from market.data.historical.calendar import MarketSessionCalendar
from market.data.historical.nse_calendar import NSETradingCalendar
from market.data.historical.liquidity import (
    DailyLiquidity,
    LiquidityMeasurement,
    LiquidityPolicy,
    is_liquid,
    rolling_liquidity,
)
from market.data.historical.universe import (
    UniversePolicy,
    UniverseSnapshot,
    build_universe_snapshot,
)


@dataclass(frozen=True, slots=True)
class UniverseIdentityRecord:
    """Historical NSE identity and current Upstox bridge."""

    symbol: str
    isin: str
    fin_instrm_id: str
    upstox_instrument_key: str | None


@dataclass(frozen=True, slots=True)
class UniverseExclusion:
    """Explicit exclusion reason."""

    symbol: str
    reason: str


@dataclass(frozen=True, slots=True)
class PointInTimeUniverseResult:
    """Complete deterministic point-in-time universe result."""

    as_of: date
    snapshot: UniverseSnapshot
    identities: tuple[UniverseIdentityRecord, ...]
    exclusions: tuple[UniverseExclusion, ...]


def _load_upstox_identity_map(
    path: Path,
) -> dict[str, str]:
    """Load current Upstox NSE_EQ identity bridge keyed by ISIN."""
    if not path.exists():
        raise FileNotFoundError(
            f"Upstox instrument master not found: {path}"
        )

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError(
            "Upstox instrument master must contain a JSON list"
        )

    mapping: dict[str, str] = {}

    for item in payload:
        if not isinstance(item, dict):
            continue

        if (
            item.get("segment") != "NSE_EQ"
            or item.get("instrument_type") != "EQ"
        ):
            continue

        isin = str(item.get("isin", "")).strip().upper()
        instrument_key = str(
            item.get("instrument_key", "")
        ).strip()

        if not isin or not instrument_key:
            continue

        previous = mapping.get(isin)

        if previous is not None and previous != instrument_key:
            raise ValueError(
                "ambiguous current Upstox ISIN mapping: "
                f"{isin}"
            )

        mapping[isin] = instrument_key

    return mapping


def _completed_session_dates_before(
    *,
    as_of: date,
    lookback_sessions: int,
    calendar: MarketSessionCalendar,
) -> tuple[date, ...]:
    """Return the latest completed exchange sessions strictly before as_of."""
    if lookback_sessions <= 0:
        raise ValueError(
            "lookback_sessions must be greater than zero"
        )

    session_dates: list[date] = []
    current = as_of - timedelta(days=1)

    # NSE weekends/holidays are sparse, so this is deliberately bounded.
    # The bound prevents an accidental infinite loop if a calendar is
    # misconfigured while still allowing extended holiday periods.
    max_calendar_days = max(370, lookback_sessions * 20)

    for _ in range(max_calendar_days):
        if len(session_dates) >= lookback_sessions:
            break

        if calendar.get_session(current) is not None:
            session_dates.append(current)

        current -= timedelta(days=1)
    else:
        raise ValueError(
            "unable to find enough completed trading sessions before "
            f"{as_of}: requested={lookback_sessions}"
        )

    # Return chronological order because rolling_liquidity() expects
    # session observations in chronological order.
    return tuple(reversed(session_dates))


def _liquidity_measurements_by_fin_instrm_id(
    *,
    candidates,
    as_of: date,
    liquidity_policy: LiquidityPolicy,
    bhavcopy: NSEBhavcopyAdapter,
    calendar: MarketSessionCalendar | None = None,
) -> dict[str, LiquidityMeasurement]:
    """Build liquidity measurements using completed NSE sessions only."""
    calendar = calendar or NSETradingCalendar()

    session_dates = _completed_session_dates_before(
        as_of=as_of,
        lookback_sessions=liquidity_policy.lookback_sessions,
        calendar=calendar,
    )

    rows = bhavcopy.get_rows_for_dates(session_dates)

    by_id: dict[str, list[DailyLiquidity]] = {}

    candidate_ids = {
        record.fin_instrm_id
        for record in candidates
    }

    for row in rows:
        if row.fin_instrm_id not in candidate_ids:
            continue

        by_id.setdefault(
            row.fin_instrm_id,
            [],
        ).append(
            DailyLiquidity(
                session_date=row.session_date,
                observation_count=1,
                traded_value=row.traded_value,
                source="nse_bhavcopy",
            )
        )

    measurements: dict[str, LiquidityMeasurement] = {}

    for record in candidates:
        sessions = tuple(
            sorted(
                by_id.get(record.fin_instrm_id, []),
                key=lambda item: item.session_date,
            )
        )

        measurements[record.symbol] = rolling_liquidity(
            sessions,
            as_of=as_of,
            lookback_sessions=liquidity_policy.lookback_sessions,
        )

    return measurements


def build_point_in_time_universe(
    *,
    as_of: date,
    liquidity_policy: LiquidityPolicy,
    universe_policy: UniversePolicy,
    upstox_master_path: str | Path = (
        "data/reference/upstox/NSE.json.gz"
    ),
    security_master_adapter: NSESecurityMasterAdapter | None = None,
    bhavcopy_adapter: NSEBhavcopyAdapter | None = None,
    source: str = (
        "nse_security_master+nse_bhavcopy"
    ),
) -> PointInTimeUniverseResult:
    """Construct one historical universe snapshot.

    Historical membership is established from the dated NSE Security
    Master and the configured liquidity policy.

    Current Upstox mapping is used only after selection as a download
    identity bridge. Missing current Upstox identity is never interpreted
    as historical inactivity.
    """
    if not isinstance(as_of, date):
        raise TypeError("as_of must be a date")

    security_master_adapter = (
        security_master_adapter
        or NSESecurityMasterAdapter(timeout_seconds=20)
    )

    bhavcopy_adapter = (
        bhavcopy_adapter
        or NSEBhavcopyAdapter(timeout=20)
    )

    upstox_by_isin = _load_upstox_identity_map(
        Path(upstox_master_path)
    )

    security_snapshot = (
        security_master_adapter.get_snapshot(as_of)
    )

    candidates = tuple(
        sorted(
            (
                record
                for record in security_snapshot.records
                if record.exchange.strip().upper() == "NSE"
                and record.series.strip().upper() == "EQ"
            ),
            key=lambda record: (
                record.symbol,
                record.fin_instrm_id,
            ),
        )
    )

    measurements = (
        _liquidity_measurements_by_fin_instrm_id(
            candidates=candidates,
            as_of=as_of,
            liquidity_policy=liquidity_policy,
            bhavcopy=bhavcopy_adapter,
        )
    )

    selected_candidates = tuple(
        record.symbol
        for record in candidates
        if is_liquid(
            measurements[record.symbol],
            liquidity_policy,
        )
    )

    snapshot = build_universe_snapshot(
        candidates=tuple(sorted(set(selected_candidates))),
        exchange="NSE",
        as_of=as_of,
        policy=universe_policy,
        liquidity_measurements=measurements,
        liquidity_policy=liquidity_policy,
        source=source,
    )

    identities: list[UniverseIdentityRecord] = []
    exclusions: list[UniverseExclusion] = []

    selected_symbols = set(snapshot.symbols)

    for record in candidates:
        symbol = record.symbol.strip().upper()

        if symbol not in selected_symbols:
            continue

        isin = record.isin.strip().upper()
        instrument_key = upstox_by_isin.get(isin)

        if instrument_key is None:
            exclusions.append(
                UniverseExclusion(
                    symbol=symbol,
                    reason="NO_CURRENT_UPSTOX_IDENTITY_BRIDGE",
                )
            )
            continue

        identities.append(
            UniverseIdentityRecord(
                symbol=symbol,
                isin=isin,
                fin_instrm_id=record.fin_instrm_id,
                upstox_instrument_key=instrument_key,
            )
        )

    return PointInTimeUniverseResult(
        as_of=as_of,
        snapshot=snapshot,
        identities=tuple(
            sorted(
                identities,
                key=lambda item: item.symbol,
            )
        ),
        exclusions=tuple(
            sorted(
                exclusions,
                key=lambda item: (
                    item.symbol,
                    item.reason,
                ),
            )
        ),
    )
