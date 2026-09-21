import pandas as pd

from analysis import TradeErrorAnalyzer
from journal.models import TradeJournalRecord
from learning import (
    LearningConfig,
    LearningEngine,
    LearningPattern,
)
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _record(
    *,
    symbol: str = "ITC",
    pnl: float = -10.0,
    mae: float = -5.0,
    mfe: float = 1.0,
    fees: float = 1.0,
    slippage: float = 1.0,
    minute: int = 15,
) -> TradeJournalRecord:
    base_time = pd.Timestamp(
        "2026-01-01 09:15:00+05:30"
    ) + pd.Timedelta(minutes=minute - 15)

    outcome = TradeOutcome(
        symbol=symbol,
        direction=StrategyDirection.LONG,
        entry_time=base_time,
        exit_time=base_time + pd.Timedelta(minutes=5),
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        gross_pnl=pnl,
        fees=fees,
        slippage_cost=slippage,
        net_pnl=pnl,
        holding_minutes=5.0,
        mae=mae,
        mfe=mfe,
    )

    return TradeJournalRecord.from_trade_outcome(
        outcome
    )


def test_repeated_loss_becomes_learning_experience() -> None:
    records = tuple(
        _record(
            pnl=-10.0,
            minute=15 + index * 5,
        )
        for index in range(4)
    )

    analysis = TradeErrorAnalyzer().analyze(
        records
    )

    report = LearningEngine().learn(
        records,
        analysis,
    )

    losses = tuple(
        experience
        for experience in report.experiences
        if experience.pattern
        == LearningPattern.LOSS
        and experience.symbol == "ITC"
    )

    assert len(losses) == 1

    experience = losses[0]

    assert experience.evidence_count == 4
    assert experience.population_count == 4
    assert experience.occurrence_rate == 1.0
    assert len(
        experience.source_trade_ids
    ) == 4


def test_insufficient_evidence_is_ignored() -> None:
    records = (
        _record(pnl=-10.0, minute=15),
        _record(
            pnl=10.0,
            mae=-1.0,
            mfe=10.0,
            fees=0.1,
            slippage=0.1,
            minute=25,
        ),
    )

    analysis = TradeErrorAnalyzer().analyze(
        records
    )

    report = LearningEngine().learn(
        records,
        analysis,
    )

    assert report.experience_count == 0


def test_occurrence_threshold_is_enforced() -> None:
    records = (
        _record(pnl=-10.0, minute=15),
        _record(pnl=-10.0, minute=25),
        _record(
            pnl=10.0,
            mae=-1.0,
            mfe=10.0,
            fees=0.1,
            slippage=0.1,
            minute=35,
        ),
        _record(
            pnl=10.0,
            mae=-1.0,
            mfe=10.0,
            fees=0.1,
            slippage=0.1,
            minute=45,
        ),
    )

    analysis = TradeErrorAnalyzer().analyze(
        records
    )

    report = LearningEngine(
        LearningConfig(
            minimum_evidence=2,
            minimum_occurrence_rate=0.75,
        )
    ).learn(
        records,
        analysis,
    )

    assert not any(
        experience.pattern
        == LearningPattern.LOSS
        and experience.symbol == "ITC"
        for experience in report.experiences
    )


def test_symbol_specific_learning_is_separate() -> None:
    records = (
        _record(
            symbol="ITC",
            pnl=-10.0,
            minute=15,
        ),
        _record(
            symbol="ITC",
            pnl=-10.0,
            minute=25,
        ),
        _record(
            symbol="ITC",
            pnl=-10.0,
            minute=35,
        ),
        _record(
            symbol="RELIANCE",
            pnl=-10.0,
            minute=45,
        ),
        _record(
            symbol="RELIANCE",
            pnl=-10.0,
            minute=55,
        ),
        _record(
            symbol="RELIANCE",
            pnl=-10.0,
            minute=5,
        ),
    )

    analysis = TradeErrorAnalyzer().analyze(
        records
    )

    report = LearningEngine().learn(
        records,
        analysis,
    )

    symbol_losses = {
        experience.symbol
        for experience in report.experiences
        if experience.pattern
        == LearningPattern.LOSS
        and experience.symbol is not None
    }

    assert symbol_losses == {
        "ITC",
        "RELIANCE",
    }


def test_learning_is_deterministic() -> None:
    records = tuple(
        _record(
            pnl=-10.0,
            minute=15 + index * 5,
        )
        for index in range(4)
    )

    analysis = TradeErrorAnalyzer().analyze(
        records
    )

    engine = LearningEngine()

    first = engine.learn(
        records,
        analysis,
    )

    second = engine.learn(
        records,
        analysis,
    )

    assert first == second


def test_empty_learning_report() -> None:
    analysis = TradeErrorAnalyzer().analyze(
        ()
    )

    report = LearningEngine().learn(
        (),
        analysis,
    )

    assert report.experiences == ()
    assert report.experience_count == 0
