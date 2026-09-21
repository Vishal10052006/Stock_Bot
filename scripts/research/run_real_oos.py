"""Build real Research/market observations and run frozen OOS evaluation.

Input market data must be completed OHLCV candles with columns:
timestamp,symbol,open,high,low,close,volume.

The script never uses labels or future-return columns from a training dataset.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import pandas as pd

from market.candles.models import Candle
from research.corpus.archive_jsonl import HistoricalArchiveJsonlLoader
from research.corpus.adapter import archive_record_to_document
from research.evaluation.intelligence import ResearchEvaluationObservation
from research.evaluation.observation_builder import build_research_market_observations
from research.evaluation.oos import evaluate_research_oos
from research.intelligence.model import ResearchIntelligenceModel


def _load_documents(path: str | Path):
    records = HistoricalArchiveJsonlLoader().load(path)
    return tuple(archive_record_to_document(record) for record in records)


def _load_candles(path: str | Path) -> dict[str, tuple[Candle, ...]]:
    frame = pd.read_parquet(path)
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"OHLCV input is missing columns: {missing}")

    frame = frame.loc[:, sorted(required)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    if frame.empty:
        raise ValueError("OHLCV input is empty")

    result: dict[str, tuple[Candle, ...]] = {}
    for symbol, group in frame.groupby("symbol", sort=True):
        rows = []
        for item in group.sort_values("timestamp").itertuples(index=False):
            rows.append(Candle(
                symbol=symbol,
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=item.timestamp.to_pydatetime(),
                open=float(item.open),
                high=float(item.high),
                low=float(item.low),
                close=float(item.close),
                volume=float(item.volume),
            ))
        result[symbol] = tuple(rows)
    return result


def _serialize_observation(row) -> dict:
    return {
        "symbol": row.symbol,
        "decision_time": row.decision_time.isoformat(),
        "feature_available_at": row.feature_available_at.isoformat(),
        "decision_close": row.decision_close,
        "outcome_timestamp": row.outcome_timestamp.isoformat(),
        "outcome_close": row.outcome_close,
        "forward_return": row.forward_return,
        "horizon_minutes": row.horizon_minutes,
        "research_score": row.research_score,
        "research_confidence": row.research_confidence,
        "evidence_count": row.evidence_count,
        "source_document_ids": list(row.source_document_ids),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-jsonl", required=True)
    parser.add_argument("--ohlcv-parquet", required=True)
    parser.add_argument("--output", default="data/research_archive/oos_result.json")
    parser.add_argument("--horizon-minutes", type=int, default=30)
    parser.add_argument("--train-size", type=int, default=200)
    parser.add_argument("--validation-size", type=int, default=50)
    parser.add_argument("--test-size", type=int, default=50)
    parser.add_argument("--purge-minutes", type=int, default=30)
    parser.add_argument("--require-evidence", action="store_true")
    args = parser.parse_args()

    documents = _load_documents(args.archive_jsonl)
    candles_by_symbol = _load_candles(args.ohlcv_parquet)
    model = ResearchIntelligenceModel()

    observations = []
    for symbol, candles in candles_by_symbol.items():
        symbol_documents = tuple(
            document for document in documents if symbol in document.symbols
        )
        if not symbol_documents:
            continue
        observations.extend(build_research_market_observations(
            symbol=symbol,
            candles=candles,
            documents=symbol_documents,
            horizons_minutes=(args.horizon_minutes,),
            intelligence_model=model,
            require_evidence=args.require_evidence,
        ))

    evaluation_rows = tuple(
        ResearchEvaluationObservation(
            symbol=row.symbol,
            decision_time=row.decision_time,
            feature_available_at=row.feature_available_at,
            research_score=row.research_score,
            outcome_timestamp=row.outcome_timestamp,
            forward_return=row.forward_return,
        )
        for row in observations
    )

    if not evaluation_rows:
        raise SystemExit(
            "No causal observations were produced. Check symbol overlap, "
            "historical coverage, and exact future OHLCV candles."
        )

    result = evaluate_research_oos(
        evaluation_rows,
        train_size=args.train_size,
        validation_size=args.validation_size,
        test_size=args.test_size,
        purge=timedelta(minutes=args.purge_minutes),
    )

    output = {
        "observations": len(observations),
        "symbols": sorted({row.symbol for row in observations}),
        "horizon_minutes": args.horizon_minutes,
        "oos": {
            "folds": len(result.folds),
            "decision": result.decision,
            "pooled_test_evaluation": (
                asdict(result.pooled_test_evaluation)
                if result.pooled_test_evaluation is not None
                else None
            ),
            "fold_results": [
                {
                    "fold_id": fold.fold_id,
                    "train_count": fold.train_count,
                    "validation_count": fold.validation_count,
                    "test_count": fold.test_count,
                    "evaluation": asdict(fold.evaluation),
                }
                for fold in result.folds
            ],
        },
        "observations_sample": [
            _serialize_observation(row) for row in observations[:100]
        ],
    }

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(output, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"documents: {len(documents)}")
    print(f"causal observations: {len(observations)}")
    print(f"OOS folds: {len(result.folds)}")
    print(f"result: {target}")


if __name__ == "__main__":
    main()
