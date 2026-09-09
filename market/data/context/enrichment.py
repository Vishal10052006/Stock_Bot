"""Point-in-time enrichment of stock observations with market/sector context."""

from __future__ import annotations

import numpy as np
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
    if not isinstance(data["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{name}.timestamp must be timezone-aware")
    if not pd.api.types.is_numeric_dtype(data["close"]):
        raise TypeError(f"{name}.close must be numeric")


def _localize_mapping_date(value: object, timezone: object) -> pd.Timestamp:
    """Represent an exchange-local mapping date in the observation timezone."""
    return pd.Timestamp(value).tz_localize(timezone)


def _point_in_time_sector_index(
    observations: pd.DataFrame,
    mappings: tuple[SectorMapping, ...],
) -> pd.Series:
    """Return the sector index valid at every observation timestamp."""
    validate_sector_mappings(mappings)
    timezone = observations["timestamp"].dt.tz

    mapping_rows: list[dict[str, object]] = []
    for mapping in mappings:
        effective_to = None
        if mapping.effective_to is not None:
            # SectorMapping.effective_to is inclusive for the entire exchange
            # day, so represent it as the final nanosecond of that local day.
            effective_to = (
                _localize_mapping_date(mapping.effective_to, timezone)
                + pd.Timedelta(days=1)
                - pd.Timedelta(nanoseconds=1)
            )

        mapping_rows.append(
            {
                "symbol": mapping.symbol,
                "sector_index_symbol": mapping.sector_index_symbol,
                "effective_from": _localize_mapping_date(
                    mapping.effective_from,
                    timezone,
                ),
                "effective_to": effective_to,
            }
        )

    mapping_frame = pd.DataFrame(mapping_rows)
    mapping_frame["effective_from"] = mapping_frame["effective_from"].dt.as_unit("ns")
    if mapping_frame["effective_to"].notna().any():
        mapping_frame["effective_to"] = mapping_frame["effective_to"].dt.as_unit("ns")
    mapping_frame = mapping_frame.sort_values(
        ["effective_from", "symbol"],
        kind="stable",
    )

    left = observations[["timestamp", "symbol"]].copy()
    left["timestamp"] = left["timestamp"].dt.as_unit("ns")
    left["_row_id"] = observations.index
    left = left.sort_values(["timestamp", "symbol"], kind="stable")

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

    return result.set_index("_row_id")["sector_index_symbol"].reindex(
        observations.index
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
    _validate_price_context(
        market_context,
        name="market_context",
        key_column=None,
    )

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
