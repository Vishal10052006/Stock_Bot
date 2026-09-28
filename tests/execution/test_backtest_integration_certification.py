from execution.backtest_integration_certification import (
    run_backtest_integration_certification,
)


def test_backtest_integration_certification_passes():
    report = run_backtest_integration_certification()
    assert report.passed
    assert not report.failed


def test_backtest_integration_certification_has_expected_cases():
    report = run_backtest_integration_certification()
    assert [case.name for case in report.cases] == [
        "authorized_path_uses_canonical_boundary",
        "no_trade_stays_no_trade",
        "backtest_costs_match_execution_assumptions",
        "assumption_mismatch_fails_closed",
        "chronology_and_causality_are_preserved",
        "risk_quantity_is_not_replaced_by_backtest_config",
    ]
