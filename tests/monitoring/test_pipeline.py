from monitoring.pipeline import MonitoringPipeline
from monitoring.models import ModelMonitoringSnapshot
from monitoring.risk import RiskMonitoringSnapshot
from monitoring.execution import ExecutionMonitoringSnapshot
from monitoring.strategy import StrategyMonitoringSnapshot


def test_pipeline_aggregates_domains_without_trade_authority() -> None:
    pipeline = MonitoringPipeline()
    pipeline.evaluate_model(ModelMonitoringSnapshot(
        model_version="v1.0", prediction_count=10,
        reference_probabilities=(0.1,) * 10,
        current_probabilities=(0.9,) * 10,
    ))
    pipeline.evaluate_risk(RiskMonitoringSnapshot(
        equity=100000, daily_pnl=-1500, open_positions=3,
        gross_exposure=75000, daily_loss_limit=1500,
        max_open_positions=3, max_gross_exposure=0.75,
        risk_per_trade=0.005,
    ))
    pipeline.evaluate_execution(ExecutionMonitoringSnapshot(
        order_count=10, filled_count=8, rejected_count=2,
        total_latency_seconds=1.0, total_slippage=5.0,
    ))
    pipeline.evaluate_strategy(StrategyMonitoringSnapshot(
        decisions=10, trades=2, no_trade=8, long_trades=1,
        short_trades=1, wins=1, losses=1, net_pnl=10.0,
    ))
    snapshot = pipeline.snapshot()
    assert any(a.code == "DAILY_LOSS_LIMIT_REACHED" for a in snapshot.alerts)
    assert any(a.code == "PREDICTION_DRIFT_EXCEEDED" for a in snapshot.alerts)
    assert snapshot.metrics["strategy.net_pnl"] == 10.0
