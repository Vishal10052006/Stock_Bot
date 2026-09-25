import pytest

from execution.engine import (
    ExecutionEngine,
    OrderSnapshot,
    OrderStatus,
)
from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
from execution.production import (
    ExecutionAssumptions,
    ExecutionMonitor,
    PaperSoakRunner,
    ProductionGateStatus,
    ProductionReadinessGate,
    assert_execution_backtest_parity,
    reconcile_execution_positions,
    validate_broker_contract,
    validate_kill_switch,
)
from execution.certification import (
    OperationalRunbook,
    RetryBackoffPolicy,
    validate_replay_idempotency,
)
from tests.execution.test_execution_engine import authorization, order_request


def test_broker_contract_is_validated_without_submission():
    adapter = PaperBrokerAdapter()
    report = validate_broker_contract(adapter)
    assert report.passed
    assert not report.failures


def test_partial_fill_matrix_is_observable():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            slippage_bps=0.0, fee_bps=0.0, partial_fill_ratio=0.5
        ),
        price_provider=lambda _order: 100.0,
    )
    engine = ExecutionEngine(adapter)
    request = ExecutionEngine.from_authorization(authorization(quantity=100.0), decision_id="partial-fill")
    result = engine.submit(request)
    assert result.snapshot.status is OrderStatus.PARTIALLY_FILLED
    assert result.snapshot.filled_quantity == 50.0
    assert result.snapshot.requested_quantity == 100.0


def test_rejection_matrix_is_fail_closed():
    class RejectingAdapter(PaperBrokerAdapter):
        def submit(self, order):
            return OrderSnapshot(
                broker_order_id="REJECT-1",
                client_order_id=order.client_order_id,
                status=OrderStatus.REJECTED_BROKER,
                requested_quantity=order.quantity,
                reason="broker rejected order",
            )

    engine = ExecutionEngine(RejectingAdapter())
    result = engine.submit(order_request())
    assert not result.accepted
    assert result.snapshot.status is OrderStatus.REJECTED_BROKER


def test_timeout_and_network_failure_remain_unknown_without_retry():
    class FailureAdapter(PaperBrokerAdapter):
        def __init__(self, message):
            super().__init__()
            self.message = message
            self.submitted_client_ids = []

        def submit(self, order):
            self.submitted_client_ids.append(order.client_order_id)
            raise TimeoutError(self.message)

        def get_order(self, client_order_id):
            return None

    for message in ("timeout", "network error"):
        adapter = FailureAdapter(message)
        engine = ExecutionEngine(adapter)
        result = engine.submit(order_request())
        assert result.snapshot.status is OrderStatus.UNKNOWN
        assert len(adapter.submitted_client_ids) == 1
        recovered = engine.recover_unknown(result.request.client_order_id)
        assert recovered.status is OrderStatus.UNKNOWN
        assert len(adapter.submitted_client_ids) == 1


def test_restart_recovery_rehydrates_from_broker_truth():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
        price_provider=lambda _order: 100.0,
    )
    first = ExecutionEngine(adapter)
    result = first.submit(order_request())
    assert result.filled

    second = ExecutionEngine(adapter)
    recovered = second.rehydrate((result.request.client_order_id,))
    assert recovered[result.request.client_order_id].status is OrderStatus.FILLED
    assert second.reconcile_order(result.request.client_order_id)


def test_position_reconciliation_supports_signed_positions():
    local = (PositionSnapshot("ITC", -10.0, 100.0),)
    broker = (PositionSnapshot("ITC", -10.0, 100.0),)
    report = reconcile_execution_positions(local, broker)
    assert report.safe


def test_position_reconciliation_blocks_mismatch():
    local = (PositionSnapshot("ITC", 10.0, 100.0),)
    broker = (PositionSnapshot("ITC", 9.0, 100.0),)
    report = reconcile_execution_positions(local, broker)
    assert not report.safe
    assert report.mismatches


def test_kill_switch_is_executable_and_blocks():
    assert validate_kill_switch()


def test_execution_monitor_captures_operational_metrics():
    engine = ExecutionEngine(PaperBrokerAdapter())
    monitor = ExecutionMonitor()
    result = engine.submit(order_request())
    monitor.record(result)
    snapshot = monitor.snapshot(engine)
    assert snapshot.orders == 1
    assert snapshot.filled == 1
    assert snapshot.unknown == 0
    assert monitor.collector.values("execution.latency_ms")


def test_paper_soak_runner():
    engine = ExecutionEngine(PaperBrokerAdapter())
    report = PaperSoakRunner(engine).run(
        [ExecutionEngine.from_authorization(authorization(quantity=100.0), decision_id="soak-1"),
         ExecutionEngine.from_authorization(authorization(quantity=50.0), decision_id="soak-2")]
    )
    assert report.passed
    assert report.orders == 2


def test_backtest_execution_parity():
    assumptions = ExecutionAssumptions(slippage_bps=5.0, fee_bps=2.0)
    assert_execution_backtest_parity(assumptions, assumptions)
    with pytest.raises(ValueError, match="mismatch"):
        assert_execution_backtest_parity(
            assumptions,
            ExecutionAssumptions(slippage_bps=7.0, fee_bps=2.0),
        )


def test_duplicate_replay_is_idempotent():
    engine = ExecutionEngine(PaperBrokerAdapter())
    first, second = validate_replay_idempotency(engine, order_request())
    assert first.snapshot.broker_order_id == second.snapshot.broker_order_id
    assert len(engine.journal) == 1


def test_rate_limit_backoff_is_bounded():
    policy = RetryBackoffPolicy(
        initial_seconds=0.5, multiplier=2.0, max_seconds=2.0, max_attempts=5
    )
    assert [policy.delay_for(i) for i in range(1, 6)] == [0.5, 1.0, 2.0, 2.0, 2.0]
    with pytest.raises(ValueError):
        policy.delay_for(6)


def test_operational_runbook_is_complete():
    assert OperationalRunbook().validate()


def test_production_readiness_fails_closed():
    report = ProductionReadinessGate().evaluate({})
    assert report.status is ProductionGateStatus.BLOCKED
    assert len(report.failed_gates) == len(ProductionReadinessGate.FIELDS)


def test_production_readiness_passes_only_when_all_gates_are_true():
    gates = {field: True for field in ProductionReadinessGate.FIELDS}
    report = ProductionReadinessGate().evaluate(gates)
    assert report.ready
