from execution.certification import FailureScenario
from execution.failure_recovery_certification import (
    run_failure_recovery_certification,
)
from tests.execution.test_execution_engine import order_request


def test_paper_failure_recovery_matrix_is_complete():
    report = run_failure_recovery_certification(order_request)

    assert report.complete
    assert report.failures == ()
    assert report.passed == (
        FailureScenario.TIMEOUT,
        FailureScenario.NETWORK_ERROR,
        FailureScenario.BROKER_REJECTION,
    )
