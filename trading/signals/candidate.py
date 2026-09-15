"""
Causal research trade-candidate construction.

Phase 8 provides the directional decision.
This module converts a LONG/SHORT decision into a fully specified
TradeCandidate using only decision-time market information.

Stop policy:

LONG:
    structural stop = confirmed swing_low, otherwise support_N
    ATR constraint   = entry - multiplier * ATR
    final stop       = max(structural stop, ATR constraint)

SHORT:
    structural stop = confirmed swing_high, otherwise resistance_N
    ATR constraint   = entry + multiplier * ATR
    final stop       = min(structural stop, ATR constraint)

The parameters are explicit and versioned through CandidateConfig.
"""

from __future__ import annotations

import math

import pandas as pd

from .models import (
    CandidateConfig,
    CandidateDirection,
    TradeCandidate,
)


def _finite_price(
    row: pd.Series,
    column: str,
) -> float:
    """Return a required finite positive price."""

    if column not in row.index:
        raise ValueError(
            f"candidate input is missing required column: {column}"
        )

    value = row[column]

    if pd.isna(value):
        raise ValueError(
            f"{column} must not be missing"
        )

    value = float(value)

    if not math.isfinite(value):
        raise ValueError(
            f"{column} must be finite"
        )

    if value <= 0:
        raise ValueError(
            f"{column} must be positive"
        )

    return value


def _optional_level(
    row: pd.Series,
    column: str,
) -> float | None:
    """Return a valid optional structural level."""

    if column not in row.index:
        return None

    value = row[column]

    if pd.isna(value):
        return None

    value = float(value)

    if not math.isfinite(value) or value <= 0:
        return None

    return value


def _structural_stop(
    row: pd.Series,
    direction: CandidateDirection,
    config: CandidateConfig,
    entry_price: float,
) -> float:
    """
    Select the nearest valid causal structural reference.

    Confirmed swing levels are preferred. If unavailable, the causal
    rolling support/resistance level configured by structural_lookback
    is used.

    The selected level must be on the correct side of entry.
    """

    period = config.structural_lookback

    if direction == CandidateDirection.LONG:
        swing = _optional_level(row, "swing_low")

        if swing is not None and swing < entry_price:
            return swing

        support = _optional_level(
            row,
            f"support_{period}",
        )

        if support is not None and support < entry_price:
            return support

        raise ValueError(
            "no valid LONG structural stop below entry_price"
        )

    if direction == CandidateDirection.SHORT:
        swing = _optional_level(row, "swing_high")

        if swing is not None and swing > entry_price:
            return swing

        resistance = _optional_level(
            row,
            f"resistance_{period}",
        )

        if resistance is not None and resistance > entry_price:
            return resistance

        raise ValueError(
            "no valid SHORT structural stop above entry_price"
        )

    raise ValueError(
        "direction must be LONG or SHORT"
    )


def build_candidate(
    row: pd.Series,
    direction: CandidateDirection,
    *,
    config: CandidateConfig | None = None,
) -> TradeCandidate:
    """
    Build one causal research trade candidate.

    Parameters
    ----------
    row:
        One decision-time raw market/indicator row. It must contain
        close, atr_{atr_period}, and the relevant causal structural
        levels.

    direction:
        LONG or SHORT.

    config:
        Explicit, versioned candidate/stop configuration.

    Returns
    -------
    TradeCandidate
        Fully specified entry and initial stop.

    Raises
    ------
    ValueError
        If required decision-time information is unavailable or the
        resulting stop is invalid.
    """

    if config is None:
        config = CandidateConfig()

    if not isinstance(row, pd.Series):
        raise TypeError("row must be a pandas Series")

    if direction not in (
        CandidateDirection.LONG,
        CandidateDirection.SHORT,
    ):
        raise ValueError(
            "direction must be LONG or SHORT"
        )

    for column in ("timestamp", "symbol"):
        if column not in row.index:
            raise ValueError(
                f"candidate input is missing required column: {column}"
            )

    timestamp = pd.Timestamp(row["timestamp"])

    if timestamp.tzinfo is None:
        raise ValueError(
            "timestamp must be timezone-aware"
        )

    symbol = str(row["symbol"]).strip()

    if not symbol:
        raise ValueError(
            "symbol must not be empty"
        )

    # DECISION_CLOSE is the explicit Phase 9 research entry convention.
    entry_price = _finite_price(row, "close")

    atr_column = f"atr_{config.atr_period}"
    atr_value = _finite_price(row, atr_column)

    structural_stop = _structural_stop(
        row,
        direction,
        config,
        entry_price,
    )

    atr_distance = (
        config.atr_multiplier * atr_value
    )

    if direction == CandidateDirection.LONG:
        atr_stop = entry_price - atr_distance

        if atr_stop <= 0:
            raise ValueError(
                "LONG ATR stop is not positive"
            )

        stop_price = max(
            structural_stop,
            atr_stop,
        )

    else:
        atr_stop = entry_price + atr_distance

        stop_price = min(
            structural_stop,
            atr_stop,
        )

    if direction == CandidateDirection.LONG:
        if stop_price >= entry_price:
            raise ValueError(
                "LONG stop construction produced invalid stop distance"
            )

    else:
        if stop_price <= entry_price:
            raise ValueError(
                "SHORT stop construction produced invalid stop distance"
            )

    return TradeCandidate(
        timestamp=timestamp,
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        stop_price=stop_price,
        policy_version=config.policy_version,
    )
