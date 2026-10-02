from datetime import datetime, timezone

import pytest

from multi_stock import MultiStockIntelligence
from multi_stock.ranking import rank_stocks


def _contexts():
    engine = MultiStockIntelligence()
    base = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    context = engine.build(
        timestamp=base,
        universe_symbols=["TCS", "INFY", "RELIANCE"],
        stock_contexts=[
            {
                "timestamp": base,
                "symbol": "TCS",
                "direction": "BULLISH",
                "state": "ALIGNED",
                "quality_score": 0.8,
            },
            {
                "timestamp": base,
                "symbol": "INFY",
                "direction": "BULLISH",
                "state": "ALIGNED",
                "quality_score": 0.8,
            },
            {
                "timestamp": base,
                "symbol": "RELIANCE",
                "direction": "NEUTRAL",
                "state": "MIXED",
                "quality_score": None,
            },
        ],
    )
    return context.observation.observations


def test_m01_ranking_is_deterministic_and_tie_safe():
    ranking = rank_stocks(
        timestamp=datetime(2026, 10, 2, 10, tzinfo=timezone.utc),
        observations=_contexts(),
    )
    assert [(x.rank, x.symbol, x.score) for x in ranking.ranks] == [
        (1, "INFY", 0.8),
        (2, "TCS", 0.8),
    ]
    assert ranking.excluded_symbols == ("RELIANCE",)
    assert ranking.authority == "OBSERVATION_ONLY"


def test_m01_rejects_future_observation():
    observations = list(_contexts())
    future = observations[0]
    future = type(future)(
        timestamp=datetime(2026, 10, 2, 11, tzinfo=timezone.utc),
        symbol=future.symbol,
        state=future.state,
        direction=future.direction,
        quality=future.quality,
        analytical_context=future.analytical_context,
        provenance=future.provenance,
    )
    with pytest.raises(ValueError, match="future stock observation"):
        rank_stocks(
            timestamp=datetime(2026, 10, 2, 10, tzinfo=timezone.utc),
            observations=[future],
        )


def test_m01_duplicate_observation_fails_closed():
    observations = _contexts()
    with pytest.raises(ValueError, match="duplicate stock observation"):
        rank_stocks(
            timestamp=datetime(2026, 10, 2, 10, tzinfo=timezone.utc),
            observations=[observations[0], observations[0]],
        )
