"""Causal fixed-horizon return-target construction for supervised prediction.

Return targets are research labels, not decision-time features. For each
decision observation, the target is the close-to-close return from the
decision candle close to the close of the Nth strictly-future candle.

The function deliberately keeps future prices out of the feature dataset.
Callers must perform temporal splitting/purging before model training.
"""

from __future__ import annotations

import pandas as pd


_REQUIRED_CANDLES = {"timestamp", "symbol", "close"}
_REQUIRED_DECISIONS = {"timestamp", "symbol", "close"}


def build_fixed_horizon_return_targets(
    candles: pd.DataFrame,
    decisions: pd.DataFrame,
    *,
    horizon_bars: int,
) -> pd.DataFrame:
    """Build one causal forward-return target per decision observation.

    future_timestamp is strictly later than the decision timestamp and
    future_close is the close of the exact horizon_bars-th future candle.

    Returns a frame keyed by timestamp/symbol containing:
        decision_close
        future_timestamp
        future_close
        future_return

    Rows without a complete future horizon are excluded rather than assigned
    a fabricated target.
    """
    if not isinstance(candles, pd.DataFrame):
        raise TypeError("candles must be a pandas DataFrame.")
    if not isinstance(decisions, pd.DataFrame):
        raise TypeError("decisions must be a pandas DataFrame.")
    if not isinstance(horizon_bars, int) or isinstance(horizon_bars, bool):
        raise TypeError("horizon_bars must be an integer.")
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be >= 1.")

    missing_candles = _REQUIRED_CANDLES.difference(candles.columns)
    if missing_candles:
        raise ValueError(
            f"candles is missing required columns: {sorted(missing_candles)}"
        )

    missing_decisions = _REQUIRED_DECISIONS.difference(decisions.columns)
    if missing_decisions:
        raise ValueError(
            "decisions is missing required columns: "
            f"{sorted(missing_decisions)}"
        )

    c = candles[["timestamp", "symbol", "close"]].copy()
    d = decisions[["timestamp", "symbol", "close"]].copy()

    c["timestamp"] = pd.to_datetime(c["timestamp"], errors="raise")
    d["timestamp"] = pd.to_datetime(d["timestamp"], errors="raise")
    c["close"] = pd.to_numeric(c["close"], errors="raise")
    d["close"] = pd.to_numeric(d["close"], errors="raise")

    if not isinstance(c["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("candle timestamps must be timezone-aware.")
    if not isinstance(d["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("decision timestamps must be timezone-aware.")

    if c[["timestamp", "symbol", "close"]].isna().any().any():
        raise ValueError("candles contains missing target-construction values.")
    if d[["timestamp", "symbol", "close"]].isna().any().any():
        raise ValueError("decisions contains missing target-construction values.")

    if c.duplicated(["symbol", "timestamp"], keep=False).any():
        raise ValueError("candles contains duplicate symbol/timestamp rows.")
    if d.duplicated(["symbol", "timestamp"], keep=False).any():
        raise ValueError("decisions contains duplicate symbol/timestamp rows.")

    rows: list[dict[str, object]] = []

    for symbol, group in c.groupby("symbol", sort=False):
        symbol_candles = group.sort_values("timestamp", kind="stable").reset_index(
            drop=True
        )
        symbol_decisions = d[d["symbol"] == symbol]

        for _, decision in symbol_decisions.iterrows():
            future = symbol_candles[
                symbol_candles["timestamp"] > decision["timestamp"]
            ].head(horizon_bars)

            if len(future) < horizon_bars:
                continue

            future_row = future.iloc[-1]
            decision_close = float(decision["close"])
            future_close = float(future_row["close"])

            if decision_close <= 0.0 or future_close <= 0.0:
                raise ValueError(
                    "decision and future close prices must be positive."
                )

            rows.append(
                {
                    "timestamp": decision["timestamp"],
                    "symbol": symbol,
                    "decision_close": decision_close,
                    "future_timestamp": future_row["timestamp"],
                    "future_close": future_close,
                    "future_return": future_close / decision_close - 1.0,
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "symbol",
            "decision_close",
            "future_timestamp",
            "future_close",
            "future_return",
        ],
    ).sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
