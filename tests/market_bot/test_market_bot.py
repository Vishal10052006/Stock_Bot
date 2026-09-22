"""Market Bot production contract and causality tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market.bot.contracts import MarketContext, MarketState
from market.bot.evaluation import deterministic_replay, evaluate_regimes
from market.bot.integration import build_analysis_input, build_phase5_market_context
from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.bot.breadth import BreadthEngine
from market.bot.correlation import CorrelationEngine
from market.bot.liquidity import LiquidityEngine
from market.bot.strength import MarketStrengthEngine
from market.bot.transitions import RegimeTransitionEngine
from market.bot.trend import TrendEngine


def _benchmark(n: int = 100) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")
    close = 100.0 * np.cumprod(1.0 + np.full(n, 0.001))
    return pd.DataFrame({"timestamp": ts, "close": close})


def _constituents(n: int = 100) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")
    rows = []
    for i, symbol in enumerate(("NIFTY", "AAA", "BBB", "CCC", "DDD")):
        base = 100.0 + i * 10.0
        drift = 0.001 if i % 2 == 0 else -0.0002
        close = base * np.cumprod(1.0 + np.full(n, drift))
        for t, c in zip(ts, close):
            rows.append({"timestamp": t, "symbol": symbol, "close": c, "volume": 1000 + i * 100})
    return pd.DataFrame(rows)


def _membership(n: int = 100) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")
    rows = []
    sectors = {"NIFTY": "INDEX", "AAA": "IT", "BBB": "BANK", "CCC": "IT", "DDD": "BANK"}
    for t in ts:
        for symbol, sector in sectors.items():
            rows.append({"timestamp": t, "symbol": symbol, "sector": sector})
    return pd.DataFrame(rows)


def test_trend_is_causal_and_warmup_is_unavailable():
    data = _benchmark()
    engine = TrendEngine()
    base = engine.calculate(data)
    future = data.copy()
    future.loc[len(future)] = [pd.Timestamp("2030-01-01", tz="UTC"), 1000.0]
    changed = engine.calculate(future)
    pd.testing.assert_series_equal(
        base["trend_state"],
        changed.loc[: len(base) - 1, "trend_state"],
        check_names=False,
    )


def test_breadth_orders_constituents_before_returns():
    data = _constituents(40)
    shuffled = data.sample(frac=1.0, random_state=7).reset_index(drop=True)
    result = BreadthEngine().calculate(shuffled)
    assert not result.empty
    assert set(result["breadth_state"]).issubset({"POSITIVE", "NEGATIVE", "MIXED", "UNAVAILABLE"})


def test_correlation_is_causal():
    data = _constituents(80)
    engine = CorrelationEngine(window=30, min_periods=20)
    first = engine.calculate(data, "NIFTY")
    future = pd.concat(
        [data, data.assign(timestamp=data["timestamp"] + pd.Timedelta(days=500))],
        ignore_index=True,
    )
    second = engine.calculate(future, "NIFTY")
    pd.testing.assert_frame_equal(
        first,
        second.loc[second["timestamp"] <= data["timestamp"].max()].reset_index(drop=True),
        check_dtype=False,
    )


def test_liquidity_baseline_is_shifted():
    data = _constituents(60)
    result = LiquidityEngine(window=20).calculate(data)
    assert result.iloc[:20]["liquidity_state"].eq("UNAVAILABLE").all()


def test_market_strength_is_bounded():
    result = MarketStrengthEngine(baseline_window=20).calculate(_benchmark(60))
    assert result["strength_score"].dropna().between(0.0, 1.0).all()


def test_regime_transition_is_descriptive():
    data = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=4, tz="UTC"),
        "regime": ["RANGE", "RANGE", "TREND_UP", "TREND_UP"],
    })
    result = RegimeTransitionEngine().calculate(data)
    assert result.loc[2, "transition_state"] == "RANGE->TREND_UP"
    assert result.loc[3, "transition_state"] == "NONE"


def test_market_bot_builds_context_without_modifying_analysis():
    benchmark = _benchmark(100)
    constituents = _constituents(100)
    membership = _membership(100)
    bot = MarketBot(MarketBotConfig(benchmark="NIFTY", data_version="test-data"))
    context = bot.build(
        benchmark_data=benchmark,
        constituent_data=constituents,
        sector_membership=membership,
        timeframe_data={"1D": benchmark},
    )
    assert isinstance(context, MarketContext)
    assert context.benchmark == "NIFTY"
    assert context.metadata.data_version == "test-data"
    assert context.state.availability in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}
    assert "1D" in context.multi_timeframe


def test_market_context_rejects_future_analysis_timestamp_leakage():
    benchmark = _benchmark(100)
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(benchmark_data=benchmark)
    with pytest.raises(ValueError, match="cannot be from the future"):
        build_analysis_input(
            timestamp=pd.Timestamp("2025-04-01", tz="UTC"),
            symbol="AAA",
            features={"rsi": 55.0},
            market_context=context,
        )


def test_market_context_can_enter_existing_analysis_contract():
    benchmark = _benchmark(100)
    bot = MarketBot(MarketBotConfig(benchmark="NIFTY"))
    context = bot.build(benchmark_data=benchmark)
    analysis_input = build_analysis_input(
        timestamp=pd.Timestamp("2025-04-10", tz="UTC"),
        symbol="AAA",
        features={"rsi": 55.0},
        market_context=context,
    )
    assert analysis_input.market_context["benchmark"] == "NIFTY"
    assert analysis_input.symbol == "AAA"


def test_regime_evaluation_and_replay_are_deterministic():
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=5, tz="UTC"),
        "regime": ["RANGE", "RANGE", "TREND_UP", "TREND_UP", "RANGE"],
    })
    metrics = evaluate_regimes(frame)
    assert metrics.transition_count == 2
    assert metrics.completeness == 1.0
    assert deterministic_replay(frame, frame.copy())


def test_market_state_rejects_naive_timestamp():
    with pytest.raises(ValueError):
        MarketState(timestamp=pd.Timestamp("2025-01-01").to_pydatetime(), benchmark="NIFTY")


def test_market_context_rejects_timestamp_mismatch():
    ts = pd.Timestamp("2025-01-01", tz="UTC").to_pydatetime()
    state = MarketState(timestamp=ts, benchmark="NIFTY")
    other = pd.Timestamp("2025-01-02", tz="UTC").to_pydatetime()
    with pytest.raises(ValueError):
        MarketContext(timestamp=other, benchmark="NIFTY", state=state)


def test_breadth_warmup_is_unavailable_not_mixed():
    data = _constituents(3)
    result = BreadthEngine().calculate(data)
    assert result.iloc[0]["breadth_state"] == "UNAVAILABLE"


def test_market_bot_allows_missing_benchmark_constituent():
    benchmark = _benchmark(100)
    constituents = _constituents(100)
    constituents = constituents.loc[constituents["symbol"] != "NIFTY"].copy()
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(
        benchmark_data=benchmark,
        constituent_data=constituents,
    )
    assert context.state.breadth_state in {"POSITIVE", "NEGATIVE", "MIXED"}
    assert context.state.correlation_state is None
    assert context.correlation == {}


def test_market_bot_allows_breadth_without_volume_and_marks_liquidity_unavailable():
    benchmark = _benchmark(100)
    constituents = _constituents(100).drop(columns=["volume"])
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(
        benchmark_data=benchmark,
        constituent_data=constituents,
    )
    assert context.state.breadth_state in {"POSITIVE", "NEGATIVE", "MIXED"}
    assert context.state.liquidity_state is None
    assert context.liquidity == {}


def test_market_context_store_normalizes_benchmark_key():
    from market.bot.storage import InMemoryMarketContextStore
    benchmark = _benchmark(100)
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(benchmark_data=benchmark)
    store = InMemoryMarketContextStore()
    store.put(context)
    assert store.get("nifty", context.timestamp) == context


def test_market_bot_rejects_invalid_benchmark_timestamp_and_price():
    # Use object dtype so the test fixture can represent malformed external input.
    bad_timestamp = _benchmark(5).astype({"timestamp": "object"})
    bad_timestamp.loc[0, "timestamp"] = "not-a-timestamp"
    with pytest.raises(ValueError, match="invalid values"):
        MarketBot(MarketBotConfig(benchmark="NIFTY")).build(benchmark_data=bad_timestamp)

    bad_price = _benchmark(5)
    bad_price.loc[0, "close"] = 0.0
    with pytest.raises(ValueError, match="must be positive"):
        MarketBot(MarketBotConfig(benchmark="NIFTY")).build(benchmark_data=bad_price)


def test_market_input_validation_rejects_duplicate_constituent_observation():
    from market.bot.validation_pipeline import validate_market_inputs
    benchmark = _benchmark(5)
    constituents = _constituents(5)
    duplicate = pd.concat([constituents, constituents.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate timestamp/symbol"):
        validate_market_inputs(benchmark, duplicate)


def test_market_bot_rejects_empty_benchmark():
    with pytest.raises(Exception, match="benchmark data is empty"):
        MarketBot(MarketBotConfig(benchmark="NIFTY")).build(
            benchmark_data=pd.DataFrame(columns=["timestamp", "close"])
        )


def test_market_bot_readiness_requires_explicit_causal_provenance():
    from market.bot.readiness import assess_readiness
    from market.bot.contracts import MarketContextMetadata
    benchmark = _benchmark(100)
    base = MarketBot(MarketBotConfig(benchmark="NIFTY", data_version="test")).build(benchmark_data=benchmark)
    invalid = MarketContext(
        timestamp=base.timestamp,
        benchmark=base.benchmark,
        state=base.state,
        metadata=MarketContextMetadata(
            market_version=base.metadata.market_version,
            data_version=base.metadata.data_version,
            feature_version=base.metadata.feature_version,
            provenance={},
        ),
    )
    report = assess_readiness(invalid)
    assert report.causal_boundary_declared is False
    assert report.ready_for_review is False


def test_market_bot_readiness_is_not_trade_authorization():
    from market.bot.readiness import assess_readiness
    context = MarketBot(MarketBotConfig(benchmark="NIFTY", data_version="test")).build(
        benchmark_data=_benchmark(100)
    )
    report = assess_readiness(context)
    assert report.no_trade_authority is True
    assert report.ready_for_review is True


def test_regime_research_normalizes_naive_timestamps():
    from market.bot.regime_research import RegimeResearchProtocol
    data = _benchmark(40).copy()
    data["timestamp"] = data["timestamp"].dt.tz_localize(None)
    protocol = RegimeResearchProtocol(train_size=20, test_size=10, step=10)
    folds = protocol.folds(data)
    assert folds[0].train_start.tzinfo is not None


def test_regime_research_uses_walk_forward_ordering():
    from market.bot.regime_research import RegimeResearchProtocol
    data = _benchmark(40)
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    protocol = RegimeResearchProtocol(train_size=20, test_size=10, step=10)
    folds = protocol.folds(data)
    assert folds
    assert all(f.train_end < f.test_start for f in folds)


def test_market_context_adapts_to_frozen_phase5_schema():
    benchmark = _benchmark(40)
    market_context = MarketBot(
        MarketBotConfig(benchmark="NIFTY")
    ).build(benchmark_data=benchmark)
    context = build_phase5_market_context(
        benchmark,
        market_context=market_context,
    )
    assert list(context.columns) == [
        "timestamp",
        "market_return_1",
        "market_return_3",
        "market_return_12",
        "market_volatility_20",
    ]
    assert context["timestamp"].iloc[-1] == benchmark["timestamp"].iloc[-1]
    assert context["market_return_3"].iloc[-1] == pytest.approx(
        benchmark["close"].pct_change(3).iloc[-1]
    )



def test_market_context_store_selects_latest_causal_fresh_context():
    from datetime import timedelta
    from market.bot.storage import InMemoryMarketContextStore

    benchmark = _benchmark(100)
    bot = MarketBot(MarketBotConfig(benchmark="NIFTY"))
    first = bot.build(benchmark_data=benchmark.iloc[:90])
    latest = bot.build(benchmark_data=benchmark)
    store = InMemoryMarketContextStore()
    store.put(first)
    store.put(latest)

    result = store.get_latest_at_or_before(
        "nifty",
        latest.timestamp,
        max_age=timedelta(days=1),
    )
    assert result == latest


def test_market_context_store_rejects_stale_context():
    from datetime import timedelta
    from market.bot.failure import StaleMarketDataError
    from market.bot.storage import InMemoryMarketContextStore

    benchmark = _benchmark(100)
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(benchmark_data=benchmark.iloc[:80])
    store = InMemoryMarketContextStore()
    store.put(context)

    with pytest.raises(StaleMarketDataError, match="stale"):
        store.get_latest_at_or_before(
            "NIFTY",
            benchmark["timestamp"].iloc[-1].to_pydatetime(),
            max_age=timedelta(days=1),
        )


def test_market_context_store_never_returns_future_context():
    from datetime import timedelta
    from market.bot.storage import InMemoryMarketContextStore

    benchmark = _benchmark(100)
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(benchmark_data=benchmark)
    store = InMemoryMarketContextStore()
    store.put(context)

    result = store.get_latest_at_or_before(
        "NIFTY",
        benchmark["timestamp"].iloc[-1].to_pydatetime() - timedelta(minutes=1),
        max_age=timedelta(days=1),
    )
    assert result is None



def test_downstream_strategy_adapter_requires_fresh_causal_context():
    from datetime import timedelta
    from market.bot.downstream import market_context_for_strategy
    from market.bot.failure import StaleMarketDataError

    benchmark = _benchmark(100)
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(
        benchmark_data=benchmark
    )

    mapped = market_context_for_strategy(
        context,
        decision_timestamp=context.timestamp,
        max_age=timedelta(minutes=1),
    )
    assert mapped["benchmark"] == "NIFTY"
    assert mapped["state"]["availability"] in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}

    with pytest.raises(StaleMarketDataError, match="stale"):
        market_context_for_strategy(
            context,
            decision_timestamp=context.timestamp + timedelta(minutes=2),
            max_age=timedelta(minutes=1),
        )


def test_downstream_risk_adapter_rejects_future_context():
    from datetime import timedelta
    from market.bot.downstream import market_context_for_risk
    from market.bot.failure import StaleMarketDataError

    benchmark = _benchmark(100)
    context = MarketBot(MarketBotConfig(benchmark="NIFTY")).build(
        benchmark_data=benchmark
    )

    with pytest.raises(StaleMarketDataError, match="future"):
        market_context_for_risk(
            context,
            decision_timestamp=context.timestamp - timedelta(seconds=1),
            max_age=timedelta(minutes=1),
        )


def test_market_context_store_protocol_exposes_causal_latest_lookup():
    from market.bot.storage import InMemoryMarketContextStore, MarketContextStore

    store = InMemoryMarketContextStore()
    assert isinstance(store, MarketContextStore)
