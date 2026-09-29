"""Regression tests for the paper package import boundary."""


def test_backtesting_engine_imports_without_paper_package_cycle():
    from backtesting.engine import BacktestConfig

    assert BacktestConfig().quantity > 0


def test_lifecycle_import_does_not_require_experiment_executor():
    from trading.paper.lifecycle import TradeOutcome

    assert TradeOutcome.__name__ == "TradeOutcome"
