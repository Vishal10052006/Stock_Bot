"""Point-in-time enrichment of stock observations with market/sector context."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market.data.context.alignment import align_context
from market.data.context.models import SectorMapping, validate_sector_mappings
from market.data.context.sector_membership import PointInTimeSectorMembershipProvider


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
    if not isinstance(data["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{name}.timestamp must be timezone-aware")
    if not pd.api.types.is_numeric_dtype(data["close"]):
        raise TypeError(f"{name}.close must be numeric")


def _validate_context_frame(
    data: pd.DataFrame,
    *,
    name: str,
    key_column: str | None,
    required_columns: tuple[str, ...],
) -> None:
    """Validate a derived market/sector context frame.

    Context frames contain already-derived return/volatility features,
    so they must not be validated as raw OHLC price frames.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame")
    if data.empty:
        raise ValueError(f"{name} must not be empty")

    required = {"timestamp", *required_columns}
    if key_column is not None:
        required.add(key_column)

    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"{name} missing columns: {sorted(missing)}")

    if not isinstance(data["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{name}.timestamp must be timezone-aware")

    for column in required_columns:
        if not pd.api.types.is_numeric_dtype(data[column]):
            raise TypeError(f"{name}.{column} must be numeric")


def _localize_mapping_date(value: object, timezone: object) -> pd.Timestamp:
    """Represent an exchange-local mapping date in the observation timezone."""
    return pd.Timestamp(value).tz_localize(timezone)


def _point_in_time_sector_index(
    observations: pd.DataFrame,
    mappings: tuple[SectorMapping, ...],
) -> pd.Series:
    """Return the explicitly selected PIT sector index per observation."""
    validate_sector_mappings(mappings)

    provider = PointInTimeSectorMembershipProvider(mappings)

    values: list[str | None] = []
    for row in observations[["timestamp", "symbol"]].itertuples(index=False):
        values.append(
            provider.resolve(
                symbol=row.symbol,
                as_of=row.timestamp.date(),
            ).sector_index_symbol
        )

    return pd.Series(
        values,
        index=observations.index,
        dtype="string",
    )


def _stock_returns(observations: pd.DataFrame) -> pd.DataFrame:
    """Compute causal stock returns independently per symbol."""
    result = observations[["timestamp", "symbol", "close"]].copy()
    result["_row_id"] = result.index
    result = result.sort_values(["symbol", "timestamp"], kind="stable")

    grouped = result.groupby("symbol", sort=False)["close"]
    result["stock_return_1"] = grouped.pct_change(1)
    result = result.set_index("_row_id").reindex(observations.index)
    return result[["stock_return_1"]]


def enrich_market_sector_context(
    observations: pd.DataFrame,
    *,
    market_context: pd.DataFrame,
    sector_context: pd.DataFrame | None = None,
    sector_mappings: tuple[SectorMapping, ...] = (),
) -> pd.DataFrame:
    """Add causal market and sector context to stock observations.

    ``market_context`` must contain one index series identified by timestamp.
    ``sector_context`` contains multiple sector-index series identified by
    ``sector_index_symbol`` and timestamp. Sector membership is selected
    using only mappings effective on or before each observation timestamp.
    """
    _validate_price_context(
        observations,
        name="observations",
        key_column="symbol",
    )
    market_columns = (
        "return_1",
        "return_3",
        "return_12",
        "volatility_20",
    )

    # The public market-context contract uses canonical market_* names.
    # Normalize them once at the enrichment boundary to the internal
    # names consumed by align_context().
    market_context = market_context.copy()
    market_context = market_context.rename(
        columns={
            "market_return_1": "return_1",
            "market_return_3": "return_3",
            "market_return_12": "return_12",
            "market_volatility_20": "volatility_20",
        }
    )

    _validate_context_frame(
        market_context,
        name="market_context",
        key_column=None,
        required_columns=market_columns,
    )
    missing_market = set(market_columns).difference(market_context.columns)
    if missing_market:
        raise ValueError(
            "market_context missing columns: "
            f"{sorted(missing_market)}"
        )

    stock_returns = _stock_returns(observations)
    result = observations.copy()
    result["stock_return_1"] = stock_returns["stock_return_1"]

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
        result[column] = np.nan

    if sector_context is not None:
        _validate_context_frame(
            sector_context,
            name="sector_context",
            key_column="sector_index_symbol",
            required_columns=market_columns,
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

        result["_sector_index_symbol"] = _point_in_time_sector_index(
            observations,
            sector_mappings,
        )

        sector_rows = result[
            ["timestamp", "_sector_index_symbol"]
        ].rename(
            columns={"_sector_index_symbol": "sector_index_symbol"}
        )
        sector_rows["_row_id"] = sector_rows.index
        sector_rows = sector_rows.sort_values(
            ["timestamp", "sector_index_symbol"],
            kind="stable",
        )

        mapped = sector_rows.dropna(subset=["sector_index_symbol"])
        if not mapped.empty:
            sector_aligned = align_context(
                mapped,
                sector_context,
                context_columns=market_columns,
                context_key="sector_index_symbol",
            )
            sector_aligned = sector_aligned.set_index("_row_id")
            result.loc[sector_aligned.index, "sector_return_1"] = (
                sector_aligned["return_1"]
            )
            result.loc[sector_aligned.index, "sector_return_3"] = (
                sector_aligned["return_3"]
            )
            result.loc[sector_aligned.index, "sector_return_12"] = (
                sector_aligned["return_12"]
            )
            result.loc[sector_aligned.index, "sector_volatility_20"] = (
                sector_aligned["volatility_20"]
            )

        result = result.drop(columns=["_sector_index_symbol"])

    result["stock_vs_market_return_1"] = (
        result["stock_return_1"] - result["market_return_1"]
    )
    result["stock_vs_sector_return_1"] = (
        result["stock_return_1"] - result["sector_return_1"]
    )

    return result.drop(columns=["stock_return_1"])
