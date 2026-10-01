from __future__ import annotations

from types import SimpleNamespace

import pytest
import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from market.candles.models import Candle
from paper.runtime import PaperTradingConfig, PaperTradingRuntime
from paper.virtual_session import (
    VirtualAccountSnapshot,
    VirtualIntradaySession,
    VirtualIntradaySessionConfig,
)
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig
from trading.strategy.models import StrategyDirection


def _candle(ts: str, close: float = 100.0) -> Candle:
    return Candle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=pd.Timestamp(ts),
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def _orchestrator(
    *,
    stop_on_target_trades: bool = False,
    initial_equity: float = 100_000.0,
):
    engine = LivePaperEngine(
        LivePaperSessionConfig(
            symbol="RELIANCE",
            initial_equity=initial_equity,
            stop_on_target_trades=stop_on_target_trades,
        )
    )
    return SimpleNamespace(
        paper_engine=engine,
        process_candle=lambda candle: "PREDICTION",
    )


def test_virtual_session_requires_full_session_mode():
    with pytest.raises(ValueError, match="stop_on_target_trades=False"):
        VirtualIntradaySession(_orchestrator(stop_on_target_trades=True))


def test_virtual_session_requires_matching_initial_equity():
    with pytest.raises(ValueError, match="initial_equity"):
        VirtualIntradaySession(
            _orchestrator(initial_equity=50_000.0),
            config=VirtualIntradaySessionConfig(initial_equity=100_000.0),
        )


def test_virtual_account_snapshot_rejects_non_finite_values():
    with pytest.raises(ValueError, match="equity"):
        VirtualAccountSnapshot(
            timestamp=pd.Timestamp("2026-09-30 09:15:00+05:30"),
            equity=float("nan"),
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            gross_exposure=0.0,
            open_positions=0,
        )


def test_process_candle_records_virtual_account_state():
    session = VirtualIntradaySession(_orchestrator())

    prediction = session.process_candle(
        _candle("2026-09-30 09:20:00+05:30", close=123.0)
    )

    assert prediction == "PREDICTION"
    assert len(session.snapshots) == 1
    snapshot = session.snapshots[0]
    assert snapshot.timestamp == pd.Timestamp("2026-09-30 09:20:00+05:30")
    assert snapshot.equity == 100_000.0
    assert snapshot.realized_pnl == 0.0
    assert snapshot.unrealized_pnl == 0.0
    assert snapshot.gross_exposure == 0.0
    assert snapshot.open_positions == 0


def test_run_candles_rejects_non_chronological_stream():
    session = VirtualIntradaySession(_orchestrator())
    candles = [
        _candle("2026-09-30 09:20:00+05:30"),
        _candle("2026-09-30 09:15:00+05:30"),
    ]

    with pytest.raises(ValueError, match="strictly chronological"):
        session.run_candles(candles)


def test_virtual_session_uses_existing_paper_runtime():
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(
            initial_equity=100_000.0,
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )
    engine = LivePaperEngine(
        LivePaperSessionConfig(
            symbol="RELIANCE",
            initial_equity=100_000.0,
            stop_on_target_trades=False,
        )
    )
    engine.runtime = runtime

    authorization = ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-30 09:20:00+05:30"),
        symbol="RELIANCE",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="test",
        approved_quantity=10.0,
        approved_notional=1000.0,
    )
    order = runtime.submit(authorization, price=100.0)
    engine.exit_engine.open_position(
        order,
        stop_price=90.0,
        target_price=120.0,
        trade_id="TR-TEST-RUNTIME",
    )

    session = VirtualIntradaySession(
        SimpleNamespace(
            paper_engine=engine,
            process_candle=lambda candle: "PREDICTION",
        )
    )
    session.process_candle(_candle("2026-09-30 09:25:00+05:30", close=110.0))

    assert session.snapshots[0].equity == 100_100.0
    assert session.snapshots[0].unrealized_pnl == 100.0
    assert session.snapshots[0].gross_exposure == 1_100.0
    assert session.snapshots[0].open_positions == 1


def test_account_mark_uses_completed_lifecycle_pnl_and_closes_cleanly():
    engine = LivePaperEngine(
        LivePaperSessionConfig(
            symbol="RELIANCE",
            initial_equity=100_000.0,
            stop_on_target_trades=False,
        )
    )

    authorization = ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-30 09:20:00+05:30"),
        symbol="RELIANCE",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="test",
        approved_quantity=10.0,
        approved_notional=1000.0,
    )
    order = engine.runtime.submit(
        authorization,
        price=100.0,
        quantity=10.0,
    )
    position = engine.exit_engine.open_position(
        order,
        stop_price=90.0,
        target_price=120.0,
        trade_id="TR-TEST-001",
    )

    orchestrator = SimpleNamespace(
        paper_engine=engine,
        process_candle=lambda candle: "PREDICTION",
    )
    session = VirtualIntradaySession(orchestrator)

    open_mark = session._account_mark(
        timestamp=pd.Timestamp("2026-09-30 09:25:00+05:30"),
        prices={"RELIANCE": 110.0},
    )
    assert open_mark.open_positions == 1
    assert open_mark.unrealized_pnl == pytest.approx(
        (110.0 - position.fill_price) * position.quantity
    )

    outcome = engine.exit_engine.process_candle(
        _candle("2026-09-30 09:30:00+05:30", close=110.0),
        force_session_close=True,
    )[0]
    closed_mark = session._account_mark(
        timestamp=pd.Timestamp("2026-09-30 09:30:00+05:30"),
        prices={"RELIANCE": 110.0},
    )
    assert closed_mark.open_positions == 0
    assert closed_mark.unrealized_pnl == 0.0
    assert closed_mark.realized_pnl == pytest.approx(outcome.net_pnl)
    assert closed_mark.equity == pytest.approx(
        session.config.initial_equity + outcome.net_pnl
    )


def test_virtual_session_config_defaults_to_nse_session_window():
    config = VirtualIntradaySessionConfig()

    assert config.market_timezone == "Asia/Kolkata"
    assert config.session_open == "09:15"
    assert config.session_close == "15:30"


def test_virtual_session_config_rejects_invalid_session_clock():
    with pytest.raises(ValueError, match="HH:MM"):
        VirtualIntradaySessionConfig(session_open="9:15")


def test_process_candle_rejects_outside_session_window():
    session = VirtualIntradaySession(_orchestrator())

    with pytest.raises(ValueError, match="outside the configured session window"):
        session.process_candle(_candle("2026-09-30 08:55:00+05:30"))


def test_process_candle_rejects_cross_day_stream():
    session = VirtualIntradaySession(_orchestrator())
    session.process_candle(_candle("2026-09-30 09:15:00+05:30"))

    with pytest.raises(ValueError, match="multiple trading dates"):
        session.process_candle(_candle("2026-10-01 09:15:00+05:30"))


def test_finalize_replaces_pre_close_mark_with_final_closed_account(tmp_path):
    engine = LivePaperEngine(
        LivePaperSessionConfig(
            symbol="RELIANCE",
            initial_equity=100_000.0,
            stop_on_target_trades=False,
        )
    )

    authorization = ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-30 09:20:00+05:30"),
        symbol="RELIANCE",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="test",
        approved_quantity=10.0,
        approved_notional=1000.0,
    )
    order = engine.runtime.submit(
        authorization,
        price=100.0,
        quantity=10.0,
    )
    engine.exit_engine.open_position(
        order,
        stop_price=90.0,
        target_price=120.0,
        trade_id="TR-TEST-FINAL",
    )

    close_timestamp = pd.Timestamp("2026-09-30 15:30:00+05:30")
    engine._last_time = close_timestamp
    engine._candle_history = [{
        "timestamp": close_timestamp,
        "symbol": "RELIANCE",
        "open": 110.0,
        "high": 111.0,
        "low": 109.0,
        "close": 110.0,
        "volume": 1000.0,
    }]

    history = SimpleNamespace(
        frame=lambda: pd.DataFrame(
            [{"timestamp": close_timestamp, "close": 110.0}]
        )
    )
    orchestrator = SimpleNamespace(
        paper_engine=engine,
        history=history,
        process_candle=lambda candle: "PREDICTION",
    )
    session = VirtualIntradaySession(
        orchestrator,
        config=VirtualIntradaySessionConfig(
            output_dir=tmp_path,
            session_id="FINALIZE-TEST",
        ),
    )

    session._snapshots.append(
        VirtualAccountSnapshot(
            timestamp=close_timestamp,
            equity=100_100.0,
            realized_pnl=0.0,
            unrealized_pnl=100.0,
            gross_exposure=1_100.0,
            open_positions=1,
        )
    )

    result = session.finalize()

    assert result.completed_trades == 1
    assert session.snapshots[-1].open_positions == 0
    assert session.snapshots[-1].unrealized_pnl == 0.0
    assert session.snapshots[-1].realized_pnl == pytest.approx(
        result.outcomes[0].net_pnl
    )
    assert session.snapshots[-1].equity == pytest.approx(
        100_000.0 + result.outcomes[0].net_pnl
    )

    summary = (tmp_path / "FINALIZE-TEST" / "account_summary.json").read_text()
    assert '"open_positions": 0' in summary


def test_run_stops_live_feed_at_session_close_and_finalizes(tmp_path):
    """The session watchdog must stop a blocked live feed at session close."""
    from threading import Event

    class BlockingMarketData:
        def __init__(self):
            self.started = False
            self.stop_calls = 0
            self.stopped = Event()

        def start(self, symbols):
            self.started = True
            assert tuple(symbols) == ("RELIANCE",)

        def run(self):
            """Simulate a feed blocked waiting for the next websocket event."""
            self.stopped.wait(timeout=2.0)
            if not self.stopped.is_set():
                raise AssertionError(
                    "session watchdog did not stop the blocked market feed"
                )
            return
            yield  # Keep this method an iterator/generator.

        def stop(self):
            self.stop_calls += 1
            self.stopped.set()

    market_data = BlockingMarketData()

    orchestrator = _orchestrator()
    orchestrator.config = SimpleNamespace(symbol="RELIANCE")
    orchestrator.market_data = market_data

    session = VirtualIntradaySession(
        orchestrator,
        config=VirtualIntradaySessionConfig(
            output_dir=tmp_path,
            session_id="SESSION-CLOSE-WATCHDOG",
            session_open="00:00",
            session_close="00:01",
        ),
    )

    result = session.run()

    assert market_data.started is True
    assert market_data.stop_calls >= 1
    assert result.completed_trades == 0

    summary_path = (
        tmp_path
        / "SESSION-CLOSE-WATCHDOG"
        / "account_summary.json"
    )
    assert summary_path.exists()
