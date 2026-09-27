from __future__ import annotations

import gzip
import json

import pytest

from execution.adapters.upstox_instrument_master import (
    InstrumentMasterError,
    LocalUpstoxInstrumentResolver,
    load_nse_equity_master,
)


def write_master(path, payload):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def test_load_nse_equity_master_filters_to_nse_eq():
    path = __import__("pathlib").Path("tmp-master.json.gz")
    try:
        write_master(
            path,
            [
                {
                    "segment": "NSE_EQ",
                    "exchange": "NSE",
                    "instrument_type": "EQ",
                    "instrument_key": "NSE_EQ|INE123",
                    "trading_symbol": "ITC",
                    "isin": "INE123",
                    "exchange_token": "111",
                },
                {
                    "segment": "NSE_FO",
                    "exchange": "NSE",
                    "instrument_type": "FUT",
                    "instrument_key": "NSE_FO|123",
                    "trading_symbol": "ITC FUT",
                },
            ],
        )
        records = load_nse_equity_master(path)
        assert len(records) == 1
        assert records[0].symbol == "ITC"
        assert records[0].instrument_key == "NSE_EQ|INE123"
    finally:
        path.unlink(missing_ok=True)


def test_local_resolver_handles_multiple_companies():
    instruments = load_nse_equity_master_from_payload = (
        __import__("execution.adapters.upstox_instrument_master", fromlist=["MasterInstrument"])
    ).MasterInstrument

    resolver = LocalUpstoxInstrumentResolver(
        (
            load_nse_equity_master_from_payload(
                "ITC", "NSE_EQ|INE123", "NSE", "NSE_EQ", "EQ", "ITC"
            ),
            load_nse_equity_master_from_payload(
                "TCS", "NSE_EQ|INE456", "NSE", "NSE_EQ", "EQ", "TCS"
            ),
        )
    )
    assert resolver.resolve_key("itc") == "NSE_EQ|INE123"
    assert resolver.resolve_key("TCS") == "NSE_EQ|INE456"


def test_local_resolver_rejects_ambiguous_symbol():
    from execution.adapters.upstox_instrument_master import MasterInstrument

    with pytest.raises(InstrumentMasterError, match="ambiguous"):
        LocalUpstoxInstrumentResolver(
            (
                MasterInstrument("ITC", "NSE_EQ|A", "NSE", "NSE_EQ", "EQ", "ITC"),
                MasterInstrument("ITC", "NSE_EQ|B", "NSE", "NSE_EQ", "EQ", "ITC"),
            )
        )


def test_loader_rejects_invalid_master(tmp_path):
    path = tmp_path / "empty.json.gz"
    write_master(path, [{"segment": "BSE_EQ", "exchange": "BSE", "instrument_type": "EQ"}])
    with pytest.raises(InstrumentMasterError, match="no NSE_EQ"):
        load_nse_equity_master(path)
