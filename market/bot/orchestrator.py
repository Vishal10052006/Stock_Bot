"""Market Bot orchestration over the existing STOCK_BOT market stack."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from market.regime.detector import detect_market_regime

from .breadth import BreadthEngine
from .contracts import MarketContext, MarketContextMetadata, MarketState
from .correlation import CorrelationEngine
from .liquidity import LiquidityEngine
from .rotation import SectorRotationEngine
from .sectors import SectorEngine, rank_sector_strength
from .strength import MarketStrengthEngine
from .structure import StructureEngine
from .transitions import RegimeTransitionEngine
from .trend import TrendEngine
from .volatility import VolatilityEngine


@dataclass(frozen=True, slots=True)
class MarketBotConfig:
    benchmark: str
    data_version: str = "unknown"
    feature_version: str = "market-features-v1"
    market_version: str = "market-bot-v1.0"
    trend: Any = None
    structure: Any = None
    volatility: Any = None
    correlation_window: int = 60
    correlation_min_periods: int = 30


class MarketBot:
    """Produce one descriptive MarketContext from causal market observations."""

    def __init__(self, config: MarketBotConfig) -> None:
        self.config = config
        self.trend_engine = TrendEngine(config.trend)
        self.structure_engine = StructureEngine(config.structure)
        self.volatility_engine = VolatilityEngine(config.volatility)
        self.breadth_engine = BreadthEngine()
        self.sector_engine = SectorEngine()
        self.rotation_engine = SectorRotationEngine()
        self.correlation_engine = CorrelationEngine(
            window=config.correlation_window,
            min_periods=config.correlation_min_periods,
        )
        self.liquidity_engine = LiquidityEngine()
        self.strength_engine = MarketStrengthEngine()
        self.transition_engine = RegimeTransitionEngine()

    def build(
        self,
        *,
        benchmark_data: pd.DataFrame,
        constituent_data: pd.DataFrame | None = None,
        sector_membership: pd.DataFrame | None = None,
        timeframe_data: dict[str, pd.DataFrame] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> MarketContext:
        """Build a causal context using only data at or before the final benchmark timestamp."""
        benchmark = self._canonical_benchmark(benchmark_data)
        timestamp = benchmark["timestamp"].iloc[-1]
        trend = self.trend_engine.calculate(benchmark)
        structure = self.structure_engine.calculate(benchmark)
        volatility = self.volatility_engine.calculate(benchmark)

        breadth = pd.DataFrame(columns=["timestamp", "breadth_state", "positive_pct"])
        sectors = pd.DataFrame()
        rotation = pd.DataFrame()
        correlation = pd.DataFrame()
        liquidity = pd.DataFrame()
        if constituent_data is not None:
            constituents = self._causal_constituents(constituent_data, timestamp)
            breadth = self.breadth_engine.calculate(constituents)
            liquidity = self.liquidity_engine.calculate(constituents)
            correlation = self.correlation_engine.calculate(constituents, self.config.benchmark)
            if sector_membership is not None:
                membership = self._causal_membership(sector_membership, timestamp)
                sectors = self.sector_engine.calculate(constituents, membership)
                if not sectors.empty:
                    sectors = rank_sector_strength(sectors)
                    rotation = self.rotation_engine.calculate(sectors)

        regime_input = self._regime_input(benchmark)
        regime = detect_market_regime(regime_input)
        transitions = self.transition_engine.calculate(regime)
        strength = self.strength_engine.calculate(benchmark, breadth)

        row = self._latest(regime, timestamp)
        trend_row = self._latest(trend, timestamp)
        structure_row = self._latest(structure, timestamp)
        volatility_row = self._latest(volatility, timestamp)
        breadth_row = self._latest(breadth, timestamp)
        sector_row = self._latest(rotation, timestamp)
        correlation_row = self._latest(correlation, timestamp)
        liquidity_row = self._latest(liquidity, timestamp)
        strength_row = self._latest(strength, timestamp)
        transition_row = self._latest(transitions, timestamp)

        states = [
            row.get("regime"),
            trend_row.get("trend_state"),
            structure_row.get("range_state"),
            volatility_row.get("volatility_state"),
            breadth_row.get("breadth_state"),
            sector_row.get("rotation_state"),
            correlation_row.get("correlation_state"),
            liquidity_row.get("liquidity_state"),
            strength_row.get("strength_state"),
        ]
        available = sum(value not in (None, "", "UNAVAILABLE") and not pd.isna(value) for value in states)
        availability = "AVAILABLE" if available >= 7 else ("PARTIAL" if available else "UNAVAILABLE")
        quality = available / len(states)

        state = MarketState(
            timestamp=timestamp.to_pydatetime(),
            benchmark=self.config.benchmark,
            trend_state=trend_row.get("trend_state"),
            trend_strength=self._bounded(trend_row.get("trend_strength")),
            range_state=structure_row.get("range_state"),
            volatility_state=volatility_row.get("volatility_state"),
            volatility_level=self._finite(volatility_row.get("volatility_level")),
            breadth_state=breadth_row.get("breadth_state"),
            sector_state=sector_row.get("rotation_state"),
            rotation_state=sector_row.get("rotation_state"),
            correlation_state=correlation_row.get("correlation_state"),
            liquidity_state=liquidity_row.get("liquidity_state"),
            strength_state=strength_row.get("strength_state"),
            strength_score=self._bounded(strength_row.get("strength_score")),
            regime=row.get("regime"),
            regime_probability=self._bounded(row.get("regime_probability")),
            transition_state=transition_row.get("transition_state"),
            quality=quality,
            availability=availability,
        )

        mtf = self._multi_timeframe(timeframe_data or {}, timestamp)
        return MarketContext(
            timestamp=timestamp.to_pydatetime(),
            benchmark=self.config.benchmark,
            state=state,
            breadth=self._record(breadth_row),
            sectors=self._sector_snapshot(sectors, timestamp),
            rotation=self._record(sector_row),
            correlation=self._record(correlation_row),
            liquidity=self._record(liquidity_row),
            strength=self._record(strength_row),
            multi_timeframe=mtf,
            metadata=MarketContextMetadata(
                market_version=self.config.market_version,
                data_version=self.config.data_version,
                feature_version=self.config.feature_version,
                provenance={
                    "causal_boundary": "information_available_at_context_timestamp",
                    "benchmark": self.config.benchmark,
                    **(provenance or {}),
                },
            ),
        )

    def _canonical_benchmark(self, data: pd.DataFrame) -> pd.DataFrame:
        required={"timestamp","close"}
        missing=required.difference(data.columns)
        if missing: raise ValueError(f"benchmark missing: {sorted(missing)}")
        frame=data.copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame=frame.sort_values("timestamp",kind="stable")
        if frame["timestamp"].duplicated().any(): raise ValueError("benchmark timestamps must be unique")
        return frame.reset_index(drop=True)

    def _causal_constituents(self,data:pd.DataFrame,cutoff:pd.Timestamp)->pd.DataFrame:
        frame=data.copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame=frame.loc[frame["timestamp"]<=cutoff].copy()
        return frame.sort_values(["symbol","timestamp"],kind="stable")

    def _causal_membership(self,data:pd.DataFrame,cutoff:pd.Timestamp)->pd.DataFrame:
        frame=data.copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame=frame.loc[frame["timestamp"]<=cutoff].copy()
        return frame.sort_values(["symbol","timestamp"],kind="stable")

    def _regime_input(self,benchmark:pd.DataFrame)->pd.DataFrame:
        frame=benchmark[["timestamp","close"]].copy()
        close=pd.to_numeric(frame["close"],errors="coerce")
        frame["market_return_3"]=close.pct_change(3)
        frame["market_return_12"]=close.pct_change(12)
        frame["market_volatility_20"]=close.pct_change().rolling(20,min_periods=20).std()
        return frame

    @staticmethod
    def _latest(frame:pd.DataFrame,timestamp:pd.Timestamp)->dict[str,Any]:
        if frame is None or frame.empty or "timestamp" not in frame.columns:
            return {}
        rows=frame.loc[pd.to_datetime(frame["timestamp"],utc=True)<=timestamp]
        if rows.empty: return {}
        row=rows.iloc[-1].to_dict()
        return {str(k):v for k,v in row.items() if k!="timestamp"}

    @staticmethod
    def _record(row:dict[str,Any])->dict[str,Any]:
        return {k: MarketBot._json_value(v) for k,v in row.items()}

    @staticmethod
    def _sector_snapshot(sectors:pd.DataFrame,timestamp:pd.Timestamp)->dict[str,Any]:
        if sectors.empty: return {}
        rows=sectors.loc[pd.to_datetime(sectors["timestamp"],utc=True)==timestamp]
        if rows.empty: rows=sectors.loc[pd.to_datetime(sectors["timestamp"],utc=True)<=timestamp].tail(1)
        return {
            "sector_count": int(rows["sector"].nunique()) if "sector" in rows else 0,
            "sectors": [
                {k: MarketBot._json_value(v) for k,v in row.items() if k!="timestamp"}
                for row in rows.head(20).to_dict("records")
            ],
        }

    def _multi_timeframe(self,timeframe_data:dict[str,pd.DataFrame],cutoff:pd.Timestamp)->dict[str,Any]:
        result={}
        for name,data in sorted(timeframe_data.items()):
            frame=data.copy()
            frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
            frame=frame.loc[frame["timestamp"]<=cutoff].sort_values("timestamp")
            if frame.empty: result[name]={"state":"UNAVAILABLE"}; continue
            trend=self.trend_engine.calculate(frame)
            row=self._latest(trend,frame["timestamp"].iloc[-1])
            result[name]={
                "timestamp":frame["timestamp"].iloc[-1].isoformat(),
                "trend_state":row.get("trend_state"),
                "trend_strength":self._bounded(row.get("trend_strength")),
            }
        return result

    @staticmethod
    def _finite(value:Any)->float|None:
        if value is None or pd.isna(value): return None
        value=float(value)
        return value if np.isfinite(value) else None

    @staticmethod
    def _bounded(value:Any)->float|None:
        value=MarketBot._finite(value)
        return None if value is None else float(np.clip(value,0.0,1.0))

    @staticmethod
    def _json_value(value:Any)->Any:
        if value is None or value is pd.NA: return None
        if isinstance(value,(np.generic,)): value=value.item()
        if isinstance(value,(pd.Timestamp,)): return value.isoformat()
        if isinstance(value,float) and not np.isfinite(value): return None
        if isinstance(value,(list,tuple)): return [MarketBot._json_value(v) for v in value]
        return value
