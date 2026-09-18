"""Canonical NSE sector-index registry used by Phase 9 context enrichment.

The registry separates canonical index identifiers from provider-specific
identifiers. Sector membership is intentionally not embedded here because
membership is a point-in-time data problem and must be supplied separately
as SectorMapping records sourced from an authoritative snapshot.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


DEFAULT_YFINANCE_INDEX_SYMBOLS: Mapping[str, str] = MappingProxyType(
    {
        "NIFTY50": "^NSEI",
        "NIFTY_AUTO": "^CNXAUTO",
        "NIFTY_BANK": "^NSEBANK",
        "NIFTY_FINANCIAL_SERVICES": "NIFTY_FIN_SERVICE.NS",
        "NIFTY_FMCG": "^CNXFMCG",
        "NIFTY_IT": "^CNXIT",
        "NIFTY_MEDIA": "^CNXMEDIA",
        "NIFTY_METAL": "^CNXMETAL",
        "NIFTY_PHARMA": "^CNXPHARMA",
        "NIFTY_PSU_BANK": "^CNXPSUBANK",
        "NIFTY_REALTY": "^CNXREALTY",
        "NIFTY_OIL_AND_GAS": "NIFTY_OIL_AND_GAS.NS",
        "NIFTY_HEALTHCARE": "NIFTY_HEALTHCARE.NS",
        "NIFTY_CONSUMER_DURABLES": "NIFTY_CONSR_DURBL.NS",
        "NIFTY_COMMODITIES": "^CNXCMDT",
        "NIFTY_CPSE": "NIFTY_CPSE.NS",
        "NIFTY_ENERGY": "^CNXENERGY",
        "NIFTY_INFRASTRUCTURE": "^CNXINFRA",
        "NIFTY_MNC": "^CNXMNC",
        "NIFTY_PSE": "^CNXPSE",
        "NIFTY_SERVICES_SECTOR": "^CNXSERVICE",
    }
)


SECTOR_INDEX_SYMBOLS: tuple[str, ...] = tuple(
    symbol for symbol in DEFAULT_YFINANCE_INDEX_SYMBOLS if symbol != "NIFTY50"
)


def provider_symbols_for(
    symbols: tuple[str, ...] = SECTOR_INDEX_SYMBOLS,
) -> dict[str, str]:
    """Return a normalized provider-symbol mapping for requested indices."""
    normalized = tuple(symbol.strip().upper() for symbol in symbols)
    unknown = sorted(
        symbol
        for symbol in normalized
        if symbol not in DEFAULT_YFINANCE_INDEX_SYMBOLS
    )
    if unknown:
        raise ValueError(
            "unsupported canonical NSE index symbols: "
            f"{unknown}"
        )
    return {
        symbol: DEFAULT_YFINANCE_INDEX_SYMBOLS[symbol]
        for symbol in normalized
    }
