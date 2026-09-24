"""EMP-03 — Build the frozen Strategy-Ready paper dataset.

Pipeline:
    raw OHLCV
      -> per-symbol Phase 4 IndicatorEngine
      -> Phase 5 causal features + point-in-time market context
      -> Phase 6 causal market regime
      -> strategy-ready decision-time rows
      -> Parquet + lineage manifest

This module intentionally reuses the existing Phase 4/5/6 authorities.
It does not implement a second indicator, feature, or regime formula.

The output schema contains the complete causal decision-time inputs consumed
by the authoritative PaperDecisionLoop and Strategy -> Candidate -> Risk
boundary:
    timestamp, symbol, close, regime, regime_probability,
    vwap_distance_pct, rvol_20, higher_high, higher_low,
    lower_low, lower_high, atr_14, swing_high, swing_low,
    support_20, resistance_20

The candidate/risk columns are carried from the canonical Phase 4
IndicatorEngine output. They are not recomputed in this script.

No Phase 7 labels, model predictions, strategy decisions, or future outcome
fields are included.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market.data.context import build_context_returns  # noqa: E402
from market.features.builder import build_features  # noqa: E402
from market.indicators.engine import IndicatorEngine  # noqa: E402
from market.regime.detector import detect_market_regime  # noqa: E402


REQUIRED_OHLCV = (
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

STRATEGY_READY_COLUMNS = (
    "timestamp",
    "symbol",
    "close",
    "regime",
    "regime_probability",
    "vwap_distance_pct",
    "rvol_20",
    "higher_high",
    "higher_low",
    "lower_low",
    "lower_high",
    "atr_14",
    "swing_high",
    "swing_low",
    "support_20",
    "resistance_20",
)

DEFAULT_MARKET_SYMBOL = "NIFTY 50"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_symbol(value: object) -> str:
    return str(value).strip().upper()


def _symbol_key(value: object) -> str:
    return "".join(
        character
        for character in _normalise_symbol(value)
        if character.isalnum()
    )


def _validate_ohlcv(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame")

    missing = sorted(set(REQUIRED_OHLCV).difference(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing OHLCV columns: {missing}")
    if frame.empty:
        raise ValueError(f"{name} is empty")

    result = frame.loc[:, list(REQUIRED_OHLCV)].copy()
    result["timestamp"] = pd.to_datetime(
        result["timestamp"], utc=True, errors="raise"
    )
    result["symbol"] = result["symbol"].map(_normalise_symbol)

    if result["symbol"].eq("").any():
        raise ValueError(f"{name} contains an empty symbol")

    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="raise")

    if result[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise ValueError(f"{name} contains null OHLCV values")

    if (~np.isfinite(result[["open", "high", "low", "close", "volume"]])).any().any():
        raise ValueError(f"{name} contains non-finite OHLCV values")

    if (result["close"] <= 0).any():
        raise ValueError(f"{name}.close must be positive")
    if (result["volume"] < 0).any():
        raise ValueError(f"{name}.volume must be non-negative")
    if (result["high"] < result["low"]).any():
        raise ValueError(f"{name} contains high < low rows")

    duplicate = result.duplicated(["symbol", "timestamp"], keep=False)
    if duplicate.any():
        examples = (
            result.loc[duplicate, ["symbol", "timestamp"]]
            .head(5)
            .to_dict("records")
        )
        raise ValueError(
            f"{name} contains duplicate symbol/timestamp observations: {examples}"
        )

    return result.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    ).reset_index(drop=True)


def _resolve_market_symbol(symbols: pd.Series, requested: str) -> str:
    requested_key = _symbol_key(requested)
    candidates = {
        requested_key,
        "NIFTY50",
        "NSENIFTY50",
        "NIFTY50INDEX",
    }
    matches = [
        symbol
        for symbol in symbols.drop_duplicates().tolist()
        if _symbol_key(symbol) in candidates
    ]
    if not matches:
        raise ValueError(
            "No NIFTY 50 benchmark series was found. Supply --market-parquet "
            "with the benchmark OHLCV or include the benchmark in "
            "--ohlcv-parquet and set --market-symbol."
        )
    if requested_key not in {"NIFTY50", "NSENIFTY50"}:
        exact = [s for s in matches if _symbol_key(s) == requested_key]
        if exact:
            return exact[0]
    return matches[0]


def _load_frames(
    ohlcv_path: Path,
    *,
    market_path: Path | None,
    market_symbol: str,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    stock_source = _validate_ohlcv(
        pd.read_parquet(ohlcv_path),
        name="ohlcv input",
    )

    if market_path is None:
        resolved = _resolve_market_symbol(stock_source["symbol"], market_symbol)
        market = stock_source.loc[
            stock_source["symbol"].map(_symbol_key).eq(_symbol_key(resolved))
        ].copy()
        stocks = stock_source.loc[
            ~stock_source["symbol"].map(_symbol_key).eq(_symbol_key(resolved))
        ].copy()
    else:
        market = _validate_ohlcv(
            pd.read_parquet(market_path),
            name="market input",
        )
        resolved = _resolve_market_symbol(market["symbol"], market_symbol)
        market = market.loc[
            market["symbol"].map(_symbol_key).eq(_symbol_key(resolved))
        ].copy()
        stocks = stock_source.copy()

    if stocks.empty:
        raise ValueError("No stock observations remain after benchmark exclusion")

    return stocks, market, resolved


def _build_strategy_rows(
    stocks: pd.DataFrame,
    market: pd.DataFrame,
) -> pd.DataFrame:
    """Build decision-time rows through the canonical Phase 4→6 stack."""
    indicator_engine = IndicatorEngine()

    # IndicatorEngine is intentionally run one instrument at a time because
    # its EMA/RVOL families operate on a single ordered price/volume series.
    indicator_frames: list[pd.DataFrame] = []
    for symbol, group in stocks.groupby("symbol", sort=True):
        ordered = group.sort_values("timestamp", kind="stable").reset_index(drop=True)
        indicators = indicator_engine.calculate(ordered)
        indicator_frames.append(indicators)

    indicators_all = pd.concat(indicator_frames, ignore_index=True)
    indicators_all = indicators_all.sort_values(
        ["timestamp", "symbol"],
        kind="stable",
    ).reset_index(drop=True)

    market_context = build_context_returns(
        market.loc[:, ["timestamp", "symbol", "close"]].copy(),
        key_column="symbol",
        horizons=(1, 3, 12),
        volatility_window=20,
    )
    market_context = market_context.rename(
        columns={
            "return_1": "market_return_1",
            "return_3": "market_return_3",
            "return_12": "market_return_12",
            "volatility_20": "market_volatility_20",
        }
    )

    # Phase 5 market-context alignment is defined for one stock observation
    # stream at a time. Each stock has one observation per timestamp, while
    # the combined multi-symbol frame naturally has duplicate timestamps
    # across symbols. Build features per symbol rather than weakening the
    # point-in-time alignment contract.
    market_context = market_context.loc[
        :,
        [
            "timestamp",
            "market_return_1",
            "market_return_3",
            "market_return_12",
            "market_volatility_20",
        ],
    ].copy()

    feature_frames: list[pd.DataFrame] = []

    for symbol, group in indicators_all.groupby("symbol", sort=True):
        symbol_features = build_features(
            group.sort_values("timestamp", kind="stable").reset_index(drop=True),
            market_context=market_context,
        )
        feature_frames.append(symbol_features)

    if not feature_frames:
        raise ValueError("no symbol feature frames were produced")

    features = pd.concat(
        feature_frames,
        ignore_index=True,
    ).sort_values(
        ["timestamp", "symbol"],
        kind="stable",
    ).reset_index(drop=True)

    # Phase 5 FeatureDataset intentionally does not include raw close or
    # candidate/risk construction inputs. Carry those canonical decision-time
    # values into this composition boundary without changing Phase 5.
    decision_inputs = (
        indicators_all.loc[
            :,
            [
                "timestamp",
                "symbol",
                "close",
                "atr_14",
                "swing_high",
                "swing_low",
                "support_20",
                "resistance_20",
            ],
        ]
        .sort_values(["timestamp", "symbol"], kind="stable")
        .reset_index(drop=True)
    )

    if decision_inputs.duplicated(["timestamp", "symbol"]).any():
        raise ValueError(
            "indicators contain duplicate timestamp/symbol decision inputs"
        )

    features = features.merge(
        decision_inputs,
        on=["timestamp", "symbol"],
        how="left",
        validate="one_to_one",
    )

    # Warm-up rows are expected here: ATR, structure, and regime families
    # require prior observations. Do not fail on those causal warm-up NaNs;
    # the final strategy-ready projection below drops incomplete rows.
    regime = detect_market_regime(features)

    # Phase 6 is one market regime per timestamp. Join by timestamp only,
    # exactly as the existing Phase 9 pipeline does.
    decision_rows = features.merge(
        regime,
        on="timestamp",
        how="left",
        validate="many_to_one",
    )

    result = decision_rows.loc[
        :,
        list(STRATEGY_READY_COLUMNS),
    ].copy()

    # A strategy-ready row must have every required decision-time input.
    # Warm-up/unclassified rows are excluded rather than fabricated.
    required_non_null = list(STRATEGY_READY_COLUMNS)
    result = result.dropna(
        subset=required_non_null,
    ).copy()

    structure_columns = (
        "higher_high",
        "higher_low",
        "lower_low",
        "lower_high",
    )
    for column in structure_columns:
        result[column] = result[column].astype("boolean")

    invalid_structure = result.loc[
        :,
        list(structure_columns),
    ].isna().any(axis=1)
    if invalid_structure.any():
        result = result.loc[~invalid_structure].copy()

    result["regime_probability"] = pd.to_numeric(
        result["regime_probability"],
        errors="raise",
    )
    result["vwap_distance_pct"] = pd.to_numeric(
        result["vwap_distance_pct"],
        errors="raise",
    )
    result["rvol_20"] = pd.to_numeric(
        result["rvol_20"],
        errors="raise",
    )

    if ((result["regime_probability"] < 0.0) | (result["regime_probability"] > 1.0)).any():
        raise ValueError("regime_probability is outside [0, 1]")
    if (~np.isfinite(result["regime_probability"])).any():
        raise ValueError("regime_probability contains non-finite values")
    if (~np.isfinite(result["vwap_distance_pct"])).any():
        raise ValueError("vwap_distance_pct contains non-finite values")
    if (~np.isfinite(result["rvol_20"])).any():
        raise ValueError("rvol_20 contains non-finite values")

    result = result.sort_values(
        ["timestamp", "symbol"],
        kind="stable",
    ).reset_index(drop=True)

    if result.duplicated(["symbol", "timestamp"]).any():
        raise AssertionError("strategy-ready output contains duplicate observations")

    return result


def build_strategy_dataset(
    ohlcv: pd.DataFrame,
    market: pd.DataFrame,
    *,
    market_symbol: str = DEFAULT_MARKET_SYMBOL,
) -> pd.DataFrame:
    """Pure DataFrame entry point used by tests and local callers."""
    stocks = _validate_ohlcv(ohlcv, name="ohlcv input")
    benchmark = _validate_ohlcv(market, name="market input")
    resolved = _resolve_market_symbol(benchmark["symbol"], market_symbol)
    benchmark = benchmark.loc[
        benchmark["symbol"].map(_symbol_key).eq(_symbol_key(resolved))
    ].copy()

    return _build_strategy_rows(stocks, benchmark)


def write_strategy_dataset(
    *,
    ohlcv_path: Path,
    output_path: Path,
    market_path: Path | None = None,
    market_symbol: str = DEFAULT_MARKET_SYMBOL,
) -> dict[str, object]:
    """Build the dataset and write an auditable lineage manifest."""
    stocks, market, resolved_market = _load_frames(
        ohlcv_path,
        market_path=market_path,
        market_symbol=market_symbol,
    )
    result = _build_strategy_rows(stocks, market)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False)

    source_hash = _sha256(ohlcv_path)
    market_hash = _sha256(market_path) if market_path is not None else source_hash
    output_hash = _sha256(output_path)

    manifest = {
        "manifest_version": "STRATEGY-DATASET-MANIFEST-v1",
        "dataset_version": "strategy-ready-v2",
        "source": {
            "ohlcv_path": str(ohlcv_path),
            "ohlcv_sha256": source_hash,
            "market_path": str(market_path) if market_path is not None else str(ohlcv_path),
            "market_sha256": market_hash,
            "market_symbol": resolved_market,
        },
        "output": {
            "path": str(output_path),
            "sha256": output_hash,
            "rows": int(len(result)),
            "symbols": sorted(result["symbol"].unique().tolist()),
            "period_start": result["timestamp"].min().isoformat(),
            "period_end": result["timestamp"].max().isoformat(),
            "columns": list(result.columns),
        },
        "causal_components": {
            "indicator_engine": "Phase4-IndicatorEngine-v1",
            "feature_builder": "FeatureDataset-v1",
            "regime_detector": "Phase6-Regime-v1",
        },
        "causality": {
            "indicator_scope": "per_symbol",
            "market_context_alignment": "backward_point_in_time",
            "regime": "current_observation_plus_prior_volatility_baseline",
            "future_labels": False,
            "future_outcomes": False,
            "candidate_inputs": "Phase4-decision-time",
        },
    }
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the EMP-03 Strategy-Ready paper dataset."
    )
    parser.add_argument("--ohlcv-parquet", required=True)
    parser.add_argument("--market-parquet")
    parser.add_argument(
        "--market-symbol",
        default=DEFAULT_MARKET_SYMBOL,
        help="Benchmark symbol, default: NIFTY 50",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = write_strategy_dataset(
        ohlcv_path=Path(args.ohlcv_parquet),
        output_path=Path(args.output),
        market_path=Path(args.market_parquet) if args.market_parquet else None,
        market_symbol=args.market_symbol,
    )

    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
