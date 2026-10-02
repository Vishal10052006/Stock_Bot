from __future__ import annotations

from datetime import date, datetime, timezone
import gzip
import json

from market.data.historical.liquidity import LiquidityPolicy
from market.data.historical.nse_security_master import NSESecurityMasterRecord
from market.data.historical.nse_security_master_snapshot import NSESecurityMasterSnapshot
from market.data.historical.universe import UniversePolicy
from market.bot.universe import MarketBenchmark, MarketUniverseConfig
from market.data.historical.adapters.nse_bhavcopy import NSEBhavcopyRow

from multi_stock import MultiStockIntelligence


AS_OF = date(2026, 10, 2)
TIMESTAMP = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)


class FakeSecurityMaster:
    def __init__(self, snapshot: NSESecurityMasterSnapshot) -> None:
        self.snapshot = snapshot

    def get_snapshot(self, snapshot_date: date) -> NSESecurityMasterSnapshot:
        assert snapshot_date == AS_OF
        return self.snapshot


class FakeBhavcopy:
    def __init__(self, rows: tuple[NSEBhavcopyRow, ...]) -> None:
        self.rows = rows

    def get_rows_for_dates(self, session_dates: tuple[date, ...]):
        assert session_dates == (date(2026, 9, 30), date(2026, 10, 1))
        return self.rows


def _config() -> MarketUniverseConfig:
    return MarketUniverseConfig(
        benchmark=MarketBenchmark("NIFTY 50"),
        universe_policy=UniversePolicy(version="u-2026.10", name="test"),
        liquidity_policy=LiquidityPolicy(
            version="liq-2026.10",
            lookback_sessions=2,
            minimum_completed_sessions=2,
            minimum_average_traded_value=101.0,
        ),
        upstox_master_path="",
    )


def _security_snapshot() -> NSESecurityMasterSnapshot:
    return NSESecurityMasterSnapshot(
        snapshot_date=AS_OF,
        records=(
            NSESecurityMasterRecord(
                snapshot_date=AS_OF,
                fin_instrm_id="1002",
                symbol="INFY",
                series="EQ",
                isin="INE009A01021",
            ),
            NSESecurityMasterRecord(
                snapshot_date=AS_OF,
                fin_instrm_id="1001",
                symbol="TCS",
                series="EQ",
                isin="INE467B01029",
            ),
        ),
    )


def _rows() -> tuple[NSEBhavcopyRow, ...]:
    return tuple(
        NSEBhavcopyRow(
            session_date=session_date,
            fin_instrm_id=fin_id,
            isin=isin,
            symbol=symbol,
            series="EQ",
            traded_value=traded_value,
        )
        for session_date, fin_id, isin, symbol, traded_value in (
            (date(2026, 9, 30), "1001", "INE467B01029", "TCS", 150.0),
            (date(2026, 10, 1), "1001", "INE467B01029", "TCS", 250.0),
            (date(2026, 9, 30), "1002", "INE009A01021", "INFY", 80.0),
            (date(2026, 10, 1), "1002", "INE009A01021", "INFY", 120.0),
        )
    )


def _write_upstox_master(path) -> None:
    payload = [
        {
            "segment": "NSE_EQ",
            "instrument_type": "EQ",
            "isin": "INE467B01029",
            "instrument_key": "NSE_EQ|INE467B01029",
        },
        {
            "segment": "NSE_EQ",
            "instrument_type": "EQ",
            "isin": "INE009A01021",
            "instrument_key": "NSE_EQ|INE009A01021",
        },
    ]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def test_build_from_market_universe_uses_point_in_time_selection(tmp_path):
    master_path = tmp_path / "NSE.json.gz"
    _write_upstox_master(master_path)
    config = _config()
    config = MarketUniverseConfig(
        benchmark=config.benchmark,
        universe_policy=config.universe_policy,
        liquidity_policy=config.liquidity_policy,
        upstox_master_path=str(master_path),
    )

    context = MultiStockIntelligence().build_from_market_universe(
        as_of=AS_OF,
        timestamp=TIMESTAMP,
        config=config,
        security_master_adapter=FakeSecurityMaster(_security_snapshot()),
        bhavcopy_adapter=FakeBhavcopy(_rows()),
    )

    assert context.universe_symbols == ("TCS",)
    assert context.observation.universe_version == "u-2026.10"
    assert context.observation.available_count == 0
    assert context.observation.unavailable_count == 1
    assert context.observation.coverage == 0.0


def test_build_from_market_universe_keeps_unavailable_symbols_in_universe(tmp_path):
    master_path = tmp_path / "NSE.json.gz"
    _write_upstox_master(master_path)

    config = MarketUniverseConfig(
        benchmark=MarketBenchmark("NIFTY 50"),
        universe_policy=UniversePolicy(version="u-2026.10", name="test"),
        liquidity_policy=LiquidityPolicy(
            version="liq-2026.10",
            lookback_sessions=2,
            minimum_completed_sessions=2,
            minimum_average_traded_value=50.0,
        ),
        upstox_master_path=str(master_path),
    )

    context = MultiStockIntelligence().build_from_market_universe(
        as_of=AS_OF,
        timestamp=TIMESTAMP,
        config=config,
        security_master_adapter=FakeSecurityMaster(_security_snapshot()),
        bhavcopy_adapter=FakeBhavcopy(_rows()),
    )

    assert context.universe_symbols == ("INFY", "TCS")
    assert context.observation.available_count == 0
    assert context.observation.unavailable_count == 2
    assert context.observation.coverage == 0.0
    assert context.observation.provenance["causal_boundary"].endswith(
        "multi_stock.timestamp"
    )
