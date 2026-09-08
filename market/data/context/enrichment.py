"""Point-in-time enrichment of stock observations with market/sector context."""

from __future__ import annotations

import pandas as pd

from market.data.context.alignment import align_context
from market.data.context.models import SectorMapping, validate_sector_mappings


CONTEXT_FEATURE_COLUMNS: tuple[str, ...] = (
    "market_return_1",
    "market_return_3",
    "market_return_12",
    "market_volatility_20",
    "sector_return_1",
    "sector_return_3",
    "sector_return_12",
    "sector_volatility_20",
    "stock_vs_market_return_1",
    "stock_vs_sector_return_1",
)


def _validate_price_context(
    data: pd.DataFrame,
    *,
    name: str,
    key_column: str | None,
) -> None:
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame")
    if data.empty:
        raise ValueError(f"{name} must not be empty")
    required = {"timestamp", "close"}
    if key_column is not None:
        required.add(key_column)
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"{name} missing columns: {sorted(missing)}")
    if not pd.api.types.is_datetime64tz_dtype(data["timestamp"]):
        raise ValueError(f"{name}.timestamp must be timezone-aware")
    if not pd.api.types.is_numeric_dtype(data["close"]):
        raise TypeError(f"{name}.close must be numeric")


def _point_in_time_sector_index(
    observations: pd.DataFrame,
    mappings: tuple[SectorMapping, ...],
) -> pd.DataFrame:
    """Attach the sector index valid on each observation date."""
    validate_sector_mappings(mappings)

    mapping_frame = pd.DataFrame(
        [
            {
                "symbol": mapping.symbol,
                "sector_index_symbol": mapping.sector_index_symbol,
                "effective_from": pd.Timestamp(mapping.effective_from, tz="Asia/Kolkata"),
                "effective_to": (
                    pd.Timestamp(mapping.effective_to, tz="Asia/Kolkata")
                    if mapping.effective_to is not None
                    else pd.NaT
                ),
            }
            for mapping in mappings
        ]
    )

    left = observations[["timestamp", "symbol"]].copy()
    left = left.sort_values(["symbol", "timestamp"])
    mapping_frame = mapping_frame.sort_values(["symbol", "effective_from"])

    result = pd.merge_asof(
        left,
        mapping_frame,
        left_on="timestamp",
        right_on="effective_from",
        by="symbol",
        direction="backward",
        allow_exact_matches=True,
    )

    valid = result["effective_to"].isna() | (
        result["timestamp"] <= result["effective_to"]
    )
    result.loc[~valid, "sector_index_symbol"] = pd.NA

    return result


def enrich_market_sector_context(
    observations: pd.DataFrame,
    *,
    market_context: pd.DataFrame,
    sector_context: pd.DataFrame | None = None,
    sector_mappings: tuple[SectorMapping, ...] = (),
) -> pd.DataFrame:
    """Add causal market and sector context to stock observations.

    ``market_context`` must contain one series identified by timestamp.
    ``sector_context`` contains multiple sector-index series identified by
    ``sector_index_symbol`` and timestamp. Sector membership is selected
    using only mappings effective on or before each observation timestamp.
    """
    _validate_price_context(
        observations,
        name="observations",
        key_column="symbol",
    )
    _validate_price_context(
        market_context,
        name="market_context",
        key_column=None,
    )

    result = observations.copy()
    market_columns = (
        "return_1",
        "return_3",
        "return_12",
        "volatility_20",
    )
    missing_market = set(market_columns).difference(market_context.columns)
    if missing_market:
        raise ValueError(
            "market_context missing columns: "
            f"{sorted(missing_market)}"
        )

    result = align_context(
        result,
        market_context,
        context_columns=market_columns,
    )
    result = result.rename(
        columns={
            "return_1": "market_return_1",
            "return_3": "market_return_3",
            "return_12": "market_return_12",
            "volatility_20": "market_volatility_20",
        }
    )

    for column in (
        "sector_return_1",
        "sector_return_3",
        "sector_return_12",
        "sector_volatility_20",
    ):
        result[column] = float("nan")

    if sector_context is not None:
        _validate_price_context(
            sector_context,
            name="sector_context",
            key_column="sector_index_symbol",
        )
        missing_sector = set(market_columns).difference(sector_context.columns)
        if missing_sector:
            raise ValueError(
                "sector_context missing columns: "
                f"{sorted(missing_sector)}"
            )

        if not sector_mappings:
            raise ValueError(
                "sector_mappings are required when sector_context is supplied"
            )

        mapping = _point_in_time_sector_index(
            observations,
            sector_mappings,
        )

        sector_lookup = mapping[
            ["symbol", "timestamp", "sector_index_symbol"]
        ]
        sector_lookup = sector_lookup.set_index(observations.index)
        result["_sector_index_symbol"] = sector_lookup["sector_index_symbol"]

        sector_rows = result[["timestamp", "_sector_index_symbol"]].copy()
        sector_rows = sector_rows.rename(
            columns={"_sector_index_symbol": "sector_index_symbol"}
        )
        sector_rows = sector_rows.reset_index(drop=False)

        sector_aligned = align_context(
            sector_rows,
            sector_context,
            context_columns=market_columns,
            context_key="sector_index_symbol",
        )
        sector_aligned = sector_aligned.set_index("index")

        result["sector_return_1"] = sector_aligned["return_1"]
        result["sector_return_3"] = sector_aligned["return_3"]
        result["sector_return_12"] = sector_aligned["return_12"]
        result["sector_volatility_20"] = sector_aligned["volatility_20"]
        result = result.drop(columns=["_sector_index_symbol"])

    result["stock_vs_market_return_1"] = (
        result["return_1"] - result["market_return_1"]
        if "return_1" in result.columns
        else float("nan")
    )
    result["stock_vs_sector_return_1"] = float("nan")

    if "return_1" in result.columns:
        result["stock_vs_sector_return_1"] = (
            result["return_1"] - result["sector_return_1"]
        )

    return result.drop(columns=["return_1"], errors="ignore")
