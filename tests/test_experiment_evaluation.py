"""Tests for the S22 experiment evaluation boundary."""

from experiments.evaluation import evaluate_experiment_record
from experiments.record import ExperimentRecord


def _record(
    *,
    baseline_results: dict | None = None,
    model_results: dict | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        definition_fingerprint="definition-fingerprint",
        observations=10,
        label_distribution=(("LONG_SUCCESS", 4), ("NO_EDGE", 6)),
        baseline_results=baseline_results or {},
        model_results=model_results or {},
        stratified_results={},
        effective_sample_size_notes="",
        limitations=(),
        interpretation="",
        decision="INCONCLUSIVE",
        root_cause="",
        lesson="",
        next_experiment="",
    )


def test_evaluation_accepts_coherent_backtest_metrics() -> None:
    report = evaluate_experiment_record(
        _record(
            baseline_results={
                "backtest": {
                    "completed_trades": 2,
                    "metrics": {
                        "trade_count": 2,
                        "winning_trades": 1,
                        "losing_trades": 1,
                        "win_rate": 0.5,
                        "profit_factor": 1.5,
                        "maximum_drawdown": 20.0,
                    },
                }
            }
        )
    )

    assert report.valid
    assert report.metric_count == 6
    assert report.sections == ("baseline_results",)


def test_evaluation_rejects_incoherent_trade_counts() -> None:
    report = evaluate_experiment_record(
        _record(
            baseline_results={
                "backtest": {
                    "completed_trades": 3,
                    "metrics": {
                        "trade_count": 2,
                        "winning_trades": 1,
                        "losing_trades": 1,
                    },
                }
            }
        )
    )

    assert not report.valid
    assert (
        "backtest completed_trades must equal metrics.trade_count"
        in report.issues
    )


def test_evaluation_rejects_invalid_probability_metric_range() -> None:
    report = evaluate_experiment_record(
        _record(
            model_results={
                "evaluation": {
                    "accuracy": 1.2,
                    "brier_score": 0.2,
                }
            }
        )
    )

    assert not report.valid
    assert "model_results.evaluation.accuracy must be in [0, 1]" in report.issues


def test_evaluation_allows_infinite_profit_factor() -> None:
    report = evaluate_experiment_record(
        _record(
            baseline_results={
                "backtest": {
                    "completed_trades": 1,
                    "metrics": {
                        "trade_count": 1,
                        "winning_trades": 1,
                        "losing_trades": 0,
                        "profit_factor": float("inf"),
                    },
                }
            }
        )
    )

    assert report.valid


def test_evaluation_rejects_nan() -> None:
    report = evaluate_experiment_record(
        _record(
            baseline_results={
                "backtest": {
                    "metrics": {
                        "expectancy": float("nan"),
                    }
                }
            }
        )
    )

    assert not report.valid
    assert "baseline_results.backtest.metrics.expectancy must not be NaN" in report.issues
