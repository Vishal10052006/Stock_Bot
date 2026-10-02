"""Module 6 multi-stock intelligence orchestration."""
from __future__ import annotations
from collections import Counter
from typing import Any, Iterable, Mapping
import pandas as pd
from .contracts import MultiStockContext, MultiStockObservation, StockIntelligence
from market.bot.universe import MarketUniverseConfig, build_market_universe

class MultiStockIntelligence:
    """Aggregate validated stock-level context without trading authority."""
    VERSION = "multi-stock-v1"

    def build(self, *, timestamp: Any, universe_symbols: Iterable[str],
              stock_contexts: Iterable[Any] = (), universe_version: str = "unknown",
              data_version: str = "unknown", market_context: Mapping[str, Any] | None = None,
              sector_context: Mapping[str, Any] | None = None) -> MultiStockContext:
        ts = pd.Timestamp(timestamp)
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        symbols = tuple(sorted({str(symbol).strip().upper() for symbol in universe_symbols}))
        if any(not symbol for symbol in symbols):
            raise ValueError("universe_symbols must contain non-empty symbols")
        by_symbol: dict[str, StockIntelligence] = {}
        for context in stock_contexts:
            item = self._adapt(context, ts)
            if item.timestamp > ts:
                raise ValueError(f"future stock context rejected: {item.symbol}")
            if item.symbol not in symbols:
                raise ValueError(f"stock context outside declared universe: {item.symbol}")
            if item.symbol in by_symbol:
                raise ValueError(f"duplicate stock context: {item.symbol}")
            by_symbol[item.symbol] = item
        observations = tuple(by_symbol[symbol] for symbol in symbols if symbol in by_symbol)
        unavailable = len(symbols) - len(observations)
        directions = Counter(item.direction for item in observations)
        states = Counter(item.state for item in observations)
        observation = MultiStockObservation(
            timestamp=ts, symbols=symbols, observations=observations,
            available_count=len(observations), unavailable_count=unavailable,
            direction_counts=dict(sorted(directions.items())),
            state_counts=dict(sorted(states.items())),
            coverage=len(observations) / len(symbols) if symbols else 0.0,
            universe_version=universe_version, data_version=data_version,
            provenance={"source": "analysis_contexts", "module": self.VERSION,
                        "causal_boundary": "stock_context.timestamp <= multi_stock.timestamp"},
        )
        return MultiStockContext(timestamp=ts, universe_symbols=symbols,
                                 observation=observation,
                                 market_context=dict(market_context or {}),
                                 sector_context=dict(sector_context or {}))



    def build_from_market_universe(
        self,
        *,
        as_of,
        timestamp: Any,
        config: MarketUniverseConfig,
        stock_contexts: Iterable[Any] = (),
        security_master_adapter: Any = None,
        bhavcopy_adapter: Any = None,
        data_version: str = "unknown",
        market_context: Mapping[str, Any] | None = None,
        sector_context: Mapping[str, Any] | None = None,
    ) -> MultiStockContext:
        """Build from the authoritative point-in-time Market Bot universe."""
        symbols, result = build_market_universe(
            as_of=as_of,
            config=config,
            security_master_adapter=security_master_adapter,
            bhavcopy_adapter=bhavcopy_adapter,
        )
        return self.build(
            timestamp=timestamp,
            universe_symbols=symbols,
            stock_contexts=stock_contexts,
            universe_version=result.snapshot.policy_version,
            data_version=data_version,
            market_context=market_context,
            sector_context=sector_context,
        )

    @staticmethod
    def _adapt(context: Any, timestamp: pd.Timestamp) -> StockIntelligence:
        if hasattr(context, "symbol"):
            quality_value = getattr(context, "quality", None)
            if isinstance(quality_value, Mapping):
                quality_value = quality_value.get("score")
            payload = context.to_dashboard_payload() if hasattr(context, "to_dashboard_payload") else {}
            return StockIntelligence(
                timestamp=getattr(context, "timestamp", timestamp),
                symbol=str(context.symbol),
                state=str(getattr(context, "analytical_state", "UNKNOWN")),
                direction=str(getattr(context, "analytical_direction", "UNKNOWN")),
                quality=None if quality_value is None else float(quality_value),
                analytical_context=payload,
                provenance=getattr(context, "provenance", {}),
            )
        if not isinstance(context, Mapping):
            raise TypeError("stock context must be an AnalysisContext-like object or mapping")
        return StockIntelligence(
            timestamp=context.get("timestamp", timestamp),
            symbol=str(context.get("symbol", "")),
            state=str(context.get("analytical_state", context.get("state", "UNKNOWN"))),
            direction=str(context.get("analytical_direction", context.get("direction", "UNKNOWN"))),
            quality=context.get("quality_score", context.get("quality")),
            analytical_context=dict(context),
            provenance=dict(context.get("provenance", {})),
        )
