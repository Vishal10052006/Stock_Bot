from __future__ import annotations

from datetime import date, timedelta
import gzip
import json
from pathlib import Path
import zipfile
from io import BytesIO

import pandas as pd
import pytest

from market.data.historical.adapters.nse_bhavcopy import (
    NSEBhavcopyAdapter,
    NSEBhavcopyDataError,
)
from market.data.historical.liquidity import (
    LiquidityPolicy,
)
from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_snapshot import (
    NSESecurityMasterSnapshot,
)
from market.data.historical.point_in_time_universe import (
    build_point_in_time_universe,
)
from market.data.historical.universe import (
    UniversePolicy,
)


def _zip_csv(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        csv = frame.to_csv(index=False).encode("utf-8")
        archive.writestr("sample.csv", csv)

    return buffer.getvalue()


def _bhavcopy_frame(
    *,
    session_date: date,
    fin_instrm_id: str = "100",
    isin: str = "INE000A01000",
    symbol: str = "AAA",
    traded_value: float = 10_000_000_000.0,
    series: str = "EQ",
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "TradDt": session_date.isoformat(),
                "FinInstrmId": fin_instrm_id,
                "ISIN": isin,
                "TckrSymb": symbol,
                "SctySrs": series,
                "TtlTrfVal": traded_value,
            }
        ]
    )


def _security_record(
    *,
    symbol: str,
    fin_instrm_id: str,
    isin: str,
    snapshot_date: date,
    series: str = "EQ",
) -> NSESecurityMasterRecord:
    return NSESecurityMasterRecord(
        snapshot_date=snapshot_date,
        fin_instrm_id=fin_instrm_id,
        symbol=symbol,
        series=series,
        isin=isin,
        exchange="NSE",
    )


class FakeBhavcopyAdapter:
    def __init__(self, rows_by_date):
        self.rows_by_date = rows_by_date
        self.requested_dates = []

    def get_rows_for_dates(self, session_dates):
        self.requested_dates.append(tuple(session_dates))

        rows = []

        for session_date in session_dates:
            rows.extend(
                self.rows_by_date.get(
                    session_date,
                    (),
                )
            )

        return tuple(rows)


class FakeSecurityMasterAdapter:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.requested_dates = []

    def get_snapshot(self, snapshot_date):
        self.requested_dates.append(snapshot_date)
        return self.snapshot


def _upstox_master(
    path: Path,
    records,
) -> None:
    payload = []

    for symbol, isin, instrument_key in records:
        payload.append(
            {
                "segment": "NSE_EQ",
                "instrument_type": "EQ",
                "isin": isin,
                "trading_symbol": symbol,
                "instrument_key": instrument_key,
            }
        )

    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def _policy(
    *,
    minimum_average_traded_value: float = 1.0,
    lookback_sessions: int = 3,
) -> LiquidityPolicy:
    return LiquidityPolicy(
        version="liquidity_test_v1.0",
        lookback_sessions=lookback_sessions,
        minimum_completed_sessions=lookback_sessions,
        minimum_average_traded_value=(
            minimum_average_traded_value
        ),
    )


def _universe_policy() -> UniversePolicy:
    return UniversePolicy(
        version="universe_test_v1.0",
        name="test universe",
    )


def test_bhavcopy_parser_reads_eq_traded_value():
    session_date = date(2026, 9, 11)

    payload = _zip_csv(
        _bhavcopy_frame(
            session_date=session_date,
            traded_value=12_345_678_901.25,
        )
    )

    rows = NSEBhavcopyAdapter._parse(
        payload,
        session_date=session_date,
    )

    assert len(rows) == 1
    assert rows[0].session_date == session_date
    assert rows[0].fin_instrm_id == "100"
    assert rows[0].isin == "INE000A01000"
    assert rows[0].symbol == "AAA"
    assert rows[0].series == "EQ"
    assert rows[0].traded_value == 12_345_678_901.25


def test_bhavcopy_parser_filters_non_eq():
    session_date = date(2026, 9, 11)

    frame = pd.concat(
        [
            _bhavcopy_frame(
                session_date=session_date,
                fin_instrm_id="100",
                symbol="AAA",
                series="EQ",
            ),
            _bhavcopy_frame(
                session_date=session_date,
                fin_instrm_id="200",
                isin="IN0000000002",
                symbol="BOND",
                series="GB",
            ),
        ],
        ignore_index=True,
    )

    rows = NSEBhavcopyAdapter._parse(
        _zip_csv(frame),
        session_date=session_date,
    )

    assert len(rows) == 1
    assert rows[0].symbol == "AAA"


def test_bhavcopy_parser_rejects_missing_required_column():
    frame = _bhavcopy_frame(
        session_date=date(2026, 9, 11),
    ).drop(columns=["TtlTrfVal"])

    with pytest.raises(
        NSEBhavcopyDataError,
        match="missing required columns",
    ):
        NSEBhavcopyAdapter._parse(
            _zip_csv(frame),
            session_date=date(2026, 9, 11),
        )


def test_bhavcopy_parser_rejects_duplicate_fin_instrm_id():
    session_date = date(2026, 9, 11)

    frame = pd.concat(
        [
            _bhavcopy_frame(
                session_date=session_date,
                fin_instrm_id="100",
                symbol="AAA",
            ),
            _bhavcopy_frame(
                session_date=session_date,
                fin_instrm_id="100",
                symbol="BBB",
                isin="IN0000000002",
            ),
        ],
        ignore_index=True,
    )

    with pytest.raises(
        NSEBhavcopyDataError,
        match="duplicate FinInstrmId",
    ):
        NSEBhavcopyAdapter._parse(
            _zip_csv(frame),
            session_date=session_date,
        )


def test_point_in_time_universe_uses_bulk_dates_not_symbols(
    tmp_path,
):
    as_of = date(2026, 9, 15)

    records = (
        _security_record(
            symbol="AAA",
            fin_instrm_id="100",
            isin="INE000A01000",
            snapshot_date=as_of,
        ),
        _security_record(
            symbol="BBB",
            fin_instrm_id="200",
            isin="INE000B01000",
            snapshot_date=as_of,
        ),
    )

    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=as_of,
        records=records,
    )

    from market.data.historical.nse_calendar import NSETradingCalendar
    from market.data.historical.point_in_time_universe import (
        _completed_session_dates_before,
    )

    session_dates = _completed_session_dates_before(
        as_of=as_of,
        lookback_sessions=3,
        calendar=NSETradingCalendar(),
    )

    rows_by_date = {}

    for session_date in session_dates:
        rows_by_date[session_date] = (
            _make_row(
                session_date,
                "100",
                "INE000A01000",
                "AAA",
                10_000_000_000.0,
            ),
            _make_row(
                session_date,
                "200",
                "INE000B01000",
                "BBB",
                20_000_000_000.0,
            ),
        )

    security_master = FakeSecurityMasterAdapter(snapshot)
    bhavcopy = FakeBhavcopyAdapter(rows_by_date)

    upstox_path = tmp_path / "NSE.json.gz"

    _upstox_master(
        upstox_path,
        [
            (
                "AAA",
                "INE000A01000",
                "NSE_EQ|INE000A01000",
            ),
            (
                "BBB",
                "INE000B01000",
                "NSE_EQ|INE000B01000",
            ),
        ],
    )

    result = build_point_in_time_universe(
        as_of=as_of,
        liquidity_policy=_policy(),
        universe_policy=_universe_policy(),
        upstox_master_path=upstox_path,
        security_master_adapter=security_master,
        bhavcopy_adapter=bhavcopy,
    )

    assert result.as_of == as_of
    assert result.snapshot.symbols == ("AAA", "BBB")
    assert tuple(
        item.symbol
        for item in result.identities
    ) == ("AAA", "BBB")

    assert len(bhavcopy.requested_dates) == 1
    assert len(bhavcopy.requested_dates[0]) == 3

    assert all(
        requested_date < as_of
        for requested_date in bhavcopy.requested_dates[0]
    )


def test_current_upstox_mismatch_is_download_exclusion_only(
    tmp_path,
):
    as_of = date(2026, 9, 15)

    record = _security_record(
        symbol="AAA",
        fin_instrm_id="100",
        isin="INE000A01000",
        snapshot_date=as_of,
    )

    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=as_of,
        records=(record,),
    )

    from market.data.historical.nse_calendar import NSETradingCalendar
    from market.data.historical.point_in_time_universe import (
        _completed_session_dates_before,
    )

    session_dates = _completed_session_dates_before(
        as_of=as_of,
        lookback_sessions=3,
        calendar=NSETradingCalendar(),
    )

    rows_by_date = {
        session_date: (
            _make_row(
                session_date,
                "100",
                "INE000A01000",
                "AAA",
                10_000_000_000.0,
            ),
        )
        for session_date in session_dates
    }

    security_master = FakeSecurityMasterAdapter(snapshot)
    bhavcopy = FakeBhavcopyAdapter(rows_by_date)

    upstox_path = tmp_path / "NSE.json.gz"
    _upstox_master(upstox_path, [])

    result = build_point_in_time_universe(
        as_of=as_of,
        liquidity_policy=_policy(),
        universe_policy=_universe_policy(),
        upstox_master_path=upstox_path,
        security_master_adapter=security_master,
        bhavcopy_adapter=bhavcopy,
    )

    assert result.snapshot.symbols == ("AAA",)
    assert result.identities == ()

    assert result.exclusions == (
        type(result.exclusions[0])(
            symbol="AAA",
            reason="NO_CURRENT_UPSTOX_IDENTITY_BRIDGE",
        ),
    )


def test_as_of_day_is_never_requested_for_liquidity(
    tmp_path,
):
    as_of = date(2026, 9, 15)

    record = _security_record(
        symbol="AAA",
        fin_instrm_id="100",
        isin="INE000A01000",
        snapshot_date=as_of,
    )

    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=as_of,
        records=(record,),
    )

    rows_by_date = {
        as_of: (
            _make_row(
                as_of,
                "100",
                "INE000A01000",
                "AAA",
                999_999_999_999.0,
            ),
        ),
        date(2026, 9, 11): (
            _make_row(
                date(2026, 9, 11),
                "100",
                "INE000A01000",
                "AAA",
                10_000_000_000.0,
            ),
        ),
    }

    security_master = FakeSecurityMasterAdapter(snapshot)
    bhavcopy = FakeBhavcopyAdapter(rows_by_date)

    upstox_path = tmp_path / "NSE.json.gz"
    _upstox_master(
        upstox_path,
        [
            (
                "AAA",
                "INE000A01000",
                "NSE_EQ|INE000A01000",
            ),
        ],
    )

    result = build_point_in_time_universe(
        as_of=as_of,
        liquidity_policy=_policy(
            lookback_sessions=1,
            minimum_average_traded_value=1.0,
        ),
        universe_policy=_universe_policy(),
        upstox_master_path=upstox_path,
        security_master_adapter=security_master,
        bhavcopy_adapter=bhavcopy,
    )

    requested = bhavcopy.requested_dates[0]

    assert as_of not in requested
    assert result.snapshot.symbols == ("AAA",)


def test_current_upstox_mapping_is_not_used_to_create_historical_membership(
    tmp_path,
):
    as_of = date(2026, 9, 15)

    historical = _security_record(
        symbol="OLDNAME",
        fin_instrm_id="100",
        isin="INE000A01000",
        snapshot_date=as_of,
    )

    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=as_of,
        records=(historical,),
    )

    from market.data.historical.nse_calendar import NSETradingCalendar
    from market.data.historical.point_in_time_universe import (
        _completed_session_dates_before,
    )

    session_dates = _completed_session_dates_before(
        as_of=as_of,
        lookback_sessions=3,
        calendar=NSETradingCalendar(),
    )

    rows_by_date = {
        session_date: (
            _make_row(
                session_date,
                "100",
                "INE000A01000",
                "OLDNAME",
                10_000_000_000.0,
            ),
        )
        for session_date in session_dates
    }

    security_master = FakeSecurityMasterAdapter(snapshot)
    bhavcopy = FakeBhavcopyAdapter(rows_by_date)

    upstox_path = tmp_path / "NSE.json.gz"
    _upstox_master(
        upstox_path,
        [
            (
                "NEWNAME",
                "INE000A01000",
                "NSE_EQ|INE000A01000",
            ),
        ],
    )

    result = build_point_in_time_universe(
        as_of=as_of,
        liquidity_policy=_policy(),
        universe_policy=_universe_policy(),
        upstox_master_path=upstox_path,
        security_master_adapter=security_master,
        bhavcopy_adapter=bhavcopy,
    )

    assert result.snapshot.symbols == ("OLDNAME",)
    assert result.identities[0].symbol == "OLDNAME"
    assert result.identities[0].upstox_instrument_key == (
        "NSE_EQ|INE000A01000"
    )


def _make_row(
    session_date,
    fin_instrm_id,
    isin,
    symbol,
    traded_value,
):
    from market.data.historical.adapters.nse_bhavcopy import (
        NSEBhavcopyRow,
    )

    return NSEBhavcopyRow(
        session_date=session_date,
        fin_instrm_id=fin_instrm_id,
        isin=isin,
        symbol=symbol,
        series="EQ",
        traded_value=traded_value,
    )
