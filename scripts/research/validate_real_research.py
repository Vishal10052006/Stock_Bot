"""Run the complete real-data Research Bot completion gates.

This command is intentionally a single local entry point for the final
Research Bot validation. It does not alter memory/long_term_memory.json and
does not modify the canonical research archive.

Gates:
1. canonical archive loads without duplicate IDs
2. causal Research/market observations are built from real OHLCV
3. chronological OOS evaluation executes
4. RB-12 Analysis contract serializes without order/risk authority
5. structural production audit executes with the real OOS fold count

Usage:
    python scripts/research/validate_real_research.py \
      --archive-jsonl data/research_archive/historical_archive.jsonl \
      --manifest data/research_archive/manifest.json \
      --ohlcv-parquet data/research_archive/research_ohlcv_validation.parquet \
      --output data/research_archive/research_completion_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from market.candles.models import Candle
from research.corpus.archive_jsonl import HistoricalArchiveJsonlLoader
from research.corpus.adapter import archive_record_to_document
from research.corpus.builder import HistoricalResearchCorpusBuilder
from research.corpus.schema import ResearchCorpusManifest
from research.evaluation.observation_builder import build_research_market_observations
from research.evaluation.oos import evaluate_research_oos
from research.evaluation.intelligence import ResearchEvaluationObservation
from research.intelligence.model import ResearchIntelligenceModel
from research.integration.analysis_contract import ResearchAnalysisContext
from research.integration.context import ResearchContextBuilder
from research.monitoring.production_check import run_production_check


def _load_candles(path: str | Path) -> dict[str, tuple[Candle, ...]]:
    frame = pd.read_parquet(path)
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"OHLCV input is missing columns: {missing}")
    if frame.empty:
        raise ValueError("OHLCV input is empty")

    frame = frame.loc[:, sorted(required)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()

    result: dict[str, tuple[Candle, ...]] = {}
    for symbol, group in frame.groupby("symbol", sort=True):
        result[symbol] = tuple(
            Candle(
                symbol=symbol,
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=item.timestamp.to_pydatetime(),
                open=float(item.open),
                high=float(item.high),
                low=float(item.low),
                close=float(item.close),
                volume=float(item.volume),
            )
            for item in group.sort_values("timestamp").itertuples(index=False)
        )
    return result


def _manifest(path: str | Path) -> ResearchCorpusManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ResearchCorpusManifest(
        dataset_id=str(payload["dataset_id"]),
        version=str(payload["version"]),
        source=str(payload["source"]),
        accessed_at=datetime.fromisoformat(payload["accessed_at"]),
        time_start=(
            datetime.fromisoformat(payload["time_start"])
            if payload.get("time_start")
            else None
        ),
        time_end=(
            datetime.fromisoformat(payload["time_end"])
            if payload.get("time_end")
            else None
        ),
        document_count=int(payload["document_count"]),
        schema_version=str(payload.get("schema_version", "1.0")),
        metadata=payload,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-jsonl", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--ohlcv-parquet", required=True)
    parser.add_argument(
        "--output",
        default="data/research_archive/research_completion_report.json",
    )
    parser.add_argument("--horizon-minutes", type=int, default=30)
    parser.add_argument("--train-size", type=int, default=200)
    parser.add_argument("--validation-size", type=int, default=50)
    parser.add_argument("--test-size", type=int, default=50)
    parser.add_argument("--purge-minutes", type=int, default=30)
    parser.add_argument("--require-evidence", action="store_true")
    args = parser.parse_args()

    archive_path = Path(args.archive_jsonl)
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)

    records = HistoricalArchiveJsonlLoader().load(archive_path)
    documents = tuple(archive_record_to_document(record) for record in records)

    manifest = _manifest(manifest_path)
    corpus, audit = HistoricalResearchCorpusBuilder().build(
        documents,
        manifest=manifest,
    )

    candles_by_symbol = _load_candles(args.ohlcv_parquet)
    model = ResearchIntelligenceModel()
    observations = []

    for symbol, candles in candles_by_symbol.items():
        symbol_documents = tuple(
            document for document in documents if symbol in document.symbols
        )
        if not symbol_documents:
            continue

        observations.extend(
            build_research_market_observations(
                symbol=symbol,
                candles=candles,
                documents=symbol_documents,
                horizons_minutes=(args.horizon_minutes,),
                intelligence_model=model,
                require_evidence=args.require_evidence,
            )
        )

    if not observations:
        raise SystemExit(
            "No causal observations were produced. Check Research/market "
            "symbol overlap, PIT availability, and exact target candles."
        )

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

    oos = evaluate_research_oos(
        evaluation_rows,
        train_size=args.train_size,
        validation_size=args.validation_size,
        test_size=args.test_size,
        purge=timedelta(minutes=args.purge_minutes),
    )

    # Validate the RB-12 boundary on a real, causal context.
    first = observations[0]
    first_documents = tuple(
        document for document in documents if first.symbol in document.symbols
    )
    context = ResearchContextBuilder().build(
        symbol=first.symbol,
        as_of=first.decision_time,
        documents=first_documents,
    )
    intelligence = model.score_context(context)
    analysis_context = ResearchAnalysisContext.from_context(
        context,
        intelligence,
    )
    serialized_analysis = analysis_context.to_dict()

    production = run_production_check(
        corpus,
        audit,
        minimum_documents=1,
        required_sources=("nse-corporate-filings",),
        evaluated_oos_folds=len(oos.folds),
    )

    report = {
        "status": (
            "STRUCTURALLY_READY"
            if production.passed and oos.folds
            else "BLOCKED"
        ),
        "archive": {
            "records": len(records),
            "documents": corpus.document_count,
            "fingerprint": corpus.fingerprint,
            "audit": asdict(audit),
        },
        "market": {
            "symbols": sorted(candles_by_symbol),
            "rows": sum(len(rows) for rows in candles_by_symbol.values()),
        },
        "causal_observations": len(observations),
        "oos": {
            "folds": len(oos.folds),
            "decision": oos.decision,
            "pooled_test_evaluation": (
                asdict(oos.pooled_test_evaluation)
                if oos.pooled_test_evaluation is not None
                else None
            ),
        },
        "analysis_contract": {
            "contract_version": serialized_analysis["contract_version"],
            "symbol": serialized_analysis["symbol"],
            "research_version": serialized_analysis["research_version"],
            "intelligence_model_version": serialized_analysis[
                "intelligence_model_version"
            ],
            "evidence_count": serialized_analysis["evidence_count"],
            "contains_trade_authority_fields": any(
                key in serialized_analysis
                for key in (
                    "order",
                    "position_size",
                    "risk",
                    "stop_loss",
                    "target",
                )
            ),
        },
        "production_check": asdict(production),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    print("=" * 72)
    print("RESEARCH BOT — REAL COMPLETION GATES")
    print("=" * 72)
    print(f"Archive documents     : {corpus.document_count:,}")
    print(f"Corpus fingerprint    : {corpus.fingerprint}")
    print(f"OHLCV symbols         : {len(candles_by_symbol):,}")
    print(f"Causal observations   : {len(observations):,}")
    print(f"OOS folds             : {len(oos.folds):,}")
    print(f"OOS decision          : {oos.decision}")
    print(f"Analysis contract     : {serialized_analysis['contract_version']}")
    print(
        "Trade authority fields: "
        + ("FOUND" if report["analysis_contract"]["contains_trade_authority_fields"] else "NONE")
    )
    print(f"Production audit      : {production.status}")
    print(f"Report                : {output_path}")
    print("=" * 72)

    if not production.passed:
        raise SystemExit("Research Bot structural production audit is BLOCKED.")

    if not oos.folds:
        raise SystemExit("Research Bot OOS produced no executable folds.")

    if report["analysis_contract"]["contains_trade_authority_fields"]:
        raise SystemExit(
            "ResearchAnalysisContext contains forbidden trade/risk authority fields."
        )


if __name__ == "__main__":
    main()
