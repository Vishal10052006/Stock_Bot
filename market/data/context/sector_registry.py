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
        "NIFTY_PRIVATE_BANK": "NIFTY_PVT_BANK.NS",
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

DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS: Mapping[str, str] = MappingProxyType(
    {
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
)


# Deterministic model-side policy for reducing simultaneous PIT
# memberships to the single sector context represented by the existing
# sector_* feature family.
#
# This is NOT an NSE classification hierarchy. It is a feature-engineering
# policy and therefore must remain explicit, versioned, and tested.
SECTOR_CONTEXT_PRIORITY: tuple[str, ...] = (
    "NIFTY_PRIVATE_BANK",
    "NIFTY_PSU_BANK",
    "NIFTY_BANK",
    "NIFTY_AUTO",
    "NIFTY_FMCG",
    "NIFTY_IT",
    "NIFTY_MEDIA",
    "NIFTY_METAL",
    "NIFTY_OIL_AND_GAS",
    "NIFTY_PHARMA",
    "NIFTY_REALTY",
    "NIFTY_FINANCIAL_SERVICES",
)

_SECTOR_CONTEXT_PRIORITY_RANK = {
    symbol: rank
    for rank, symbol in enumerate(SECTOR_CONTEXT_PRIORITY)
}

def upstox_index_instrument_key(symbol: str) -> str:
    """Return the verified Upstox instrument key for a canonical sector index."""
    normalized = symbol.strip().upper()

    try:
        return DEFAULT_UPSTOX_INDEX_INSTRUMENT_KEYS[normalized]
    except KeyError as exc:
        raise ValueError(
            f"unsupported canonical Upstox sector index: {normalized!r}"
        ) from exc


def sector_context_priority(sector_index_symbol: str) -> int:
    """Return deterministic feature-context priority for a sector index.

    Registered NSE sector indices use the explicit model policy.
    Unknown identifiers are assigned a deterministic fallback priority
    after all registered sectors. This keeps the resolver generic for
    synthetic/test contexts without changing production ordering.
    """
    normalized = sector_index_symbol.strip().upper()

    return _SECTOR_CONTEXT_PRIORITY_RANK.get(
        normalized,
        len(SECTOR_CONTEXT_PRIORITY),
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
