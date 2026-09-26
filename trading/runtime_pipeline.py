"""Shared production composition boundary for one STOCK_BOT research run.

The application layer constructs one MonitoringRuntime here and passes that same
instance through Market Bot -> Analysis -> Prediction and Paper Decision Loop.
Monitoring remains observational; this module does not alter trading authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

import pandas as pd

from market.bot.contracts import MarketContext
from monitoring.engine import MonitoringEngine
from monitoring.journal import MonitoringJournal
from monitoring.pipeline import MonitoringPipeline
from monitoring.runtime import MonitoringRuntime
from ml.integration.analysis_prediction import PredictionContext, predict_from_analysis
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.ab30_pipeline import MarketAnalysisResult
from trading.market_bot_pipeline import build_market_analysis_from_market_bot
from trading.paper.decision_loop import PaperDecisionLoop, PaperDecisionRun


@dataclass(frozen=True, slots=True)
class TradingRuntimeResult:
    analysis: MarketAnalysisResult
    prediction: PredictionContext
    paper_run: PaperDecisionRun | None
    monitoring: dict


class TradingResearchRuntime:
    """Application-level composition root for a coherent research/paper run."""

    def __init__(
        self,
        *,
        monitoring: MonitoringRuntime | None = None,
        monitoring_journal_path: str | None = None,
    ) -> None:
        if monitoring is not None and monitoring_journal_path is not None:
            raise ValueError("provide monitoring or monitoring_journal_path, not both")
        if monitoring is not None:
            self.monitoring = monitoring
        else:
            path = monitoring_journal_path or os.getenv("STOCK_BOT_MONITORING_JOURNAL")
            if path:
                journal = MonitoringJournal(path)
                engine = MonitoringEngine(journal=journal)
                self.monitoring = MonitoringRuntime(
                    pipeline=MonitoringPipeline(engine=engine)
                )
            else:
                self.monitoring = MonitoringRuntime()
        self.paper_loop = PaperDecisionLoop(monitoring=self.monitoring)

    def market_analysis_and_prediction(
        self,
        candles: pd.DataFrame,
        *,
        symbol: str,
        benchmark_history: pd.DataFrame,
        market_context: MarketContext,
        model: LogisticOutcomeModel,
        preprocessor: FeaturePreprocessor,
        sector_context: pd.DataFrame | None = None,
        sector_mappings: tuple = (),
        data_version: str | None = None,
        feature_version: str | None = None,
        model_version: str = "phase9-logistic-v1",
    ) -> tuple[MarketAnalysisResult, PredictionContext]:
        analysis = build_market_analysis_from_market_bot(
            candles,
            symbol=symbol,
            benchmark_history=benchmark_history,
            market_context=market_context,
            sector_context=sector_context,
            sector_mappings=sector_mappings,
            data_version=data_version,
            feature_version=feature_version,
            monitoring=self.monitoring,
        )
        prediction = predict_from_analysis(
            analysis.analysis,
            model=model,
            preprocessor=preprocessor,
            model_version=model_version,
            monitoring=self.monitoring,
        )
        return analysis, prediction

    def paper_decisions(
        self,
        rows: pd.DataFrame,
        *,
        price_column: str = "close",
        quantity: float = 1.0,
    ) -> PaperDecisionRun:
        return self.paper_loop.run(rows, price_column=price_column, quantity=quantity)

    def report(self) -> dict:
        return self.monitoring.dashboard()
