import pytest

from market.data.context.sector_registry import (
    DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS,
    upstox_index_instrument_key,
)


EXPECTED_UPSTOX_KEYS = {
    "NIFTY_AUTO": "NSE_INDEX|Nifty Auto",
    "NIFTY_BANK": "NSE_INDEX|Nifty Bank",
    "NIFTY_FINANCIAL_SERVICES": "NSE_INDEX|Nifty Fin Service",
    "NIFTY_FMCG": "NSE_INDEX|Nifty FMCG",
    "NIFTY_IT": "NSE_INDEX|Nifty IT",
    "NIFTY_MEDIA": "NSE_INDEX|Nifty Media",
    "NIFTY_METAL": "NSE_INDEX|Nifty Metal",
    "NIFTY_OIL_AND_GAS": "NSE_INDEX|NIFTY OIL AND GAS",
    "NIFTY_PHARMA": "NSE_INDEX|Nifty Pharma",
    "NIFTY_PRIVATE_BANK": "NSE_INDEX|Nifty Pvt Bank",
    "NIFTY_PSU_BANK": "NSE_INDEX|Nifty PSU Bank",
    "NIFTY_REALTY": "NSE_INDEX|Nifty Realty",
}


def test_all_phase9_sector_indices_have_upstox_keys():
    assert dict(DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS) == EXPECTED_UPSTOX_KEYS


def test_all_upstox_sector_keys_are_nse_index_keys():
    for instrument_key in DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS.values():
        assert instrument_key.startswith("NSE_INDEX|")


def test_upstox_sector_index_key_is_exact():
    assert (
        upstox_index_instrument_key("NIFTY_METAL")
        == "NSE_INDEX|Nifty Metal"
    )


def test_upstox_private_bank_key():
    assert (
        upstox_index_instrument_key("NIFTY_PRIVATE_BANK")
        == "NSE_INDEX|Nifty Pvt Bank"
    )


def test_upstox_financial_services_key():
    assert (
        upstox_index_instrument_key("NIFTY_FINANCIAL_SERVICES")
        == "NSE_INDEX|Nifty Fin Service"
    )


def test_upstox_lookup_normalizes_input():
    assert (
        upstox_index_instrument_key(" nifty_metal ")
        == "NSE_INDEX|Nifty Metal"
    )


def test_unknown_sector_rejected():
    with pytest.raises(ValueError, match="unsupported canonical Upstox sector index"):
        upstox_index_instrument_key("NIFTY_UNKNOWN")