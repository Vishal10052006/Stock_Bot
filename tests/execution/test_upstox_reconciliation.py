from execution.engine import PositionSnapshot
from execution.production import reconcile_execution_positions
from execution.reconciliation import ReconciliationStatus


def test_upstox_reconciliation_matches_signed_positions():
    local = (
        PositionSnapshot("ITC", 10, 450.0),
        PositionSnapshot("TCS", -5, 3000.0),
    )
    broker = (
        PositionSnapshot("ITC", 10, 450.0),
        PositionSnapshot("TCS", -5, 3000.0),
    )
    report = reconcile_execution_positions(local, broker)
    assert report.status is ReconciliationStatus.MATCH
    assert report.safe


def test_upstox_reconciliation_blocks_missing_snapshot():
    report = reconcile_execution_positions(None, None)
    assert report.status is ReconciliationStatus.BLOCKED
    assert not report.safe


def test_upstox_reconciliation_detects_quantity_mismatch():
    local = (PositionSnapshot("ITC", 10, 450.0),)
    broker = (PositionSnapshot("ITC", 9, 450.0),)
    report = reconcile_execution_positions(local, broker)
    assert report.status is ReconciliationStatus.MISMATCH
    assert "ITC" in report.mismatches[0]


def test_upstox_reconciliation_detects_price_mismatch():
    local = (PositionSnapshot("ITC", 10, 450.0),)
    broker = (PositionSnapshot("ITC", 10, 451.0),)
    report = reconcile_execution_positions(local, broker)
    assert report.status is ReconciliationStatus.MISMATCH
    assert "ITC" in report.mismatches[0]
