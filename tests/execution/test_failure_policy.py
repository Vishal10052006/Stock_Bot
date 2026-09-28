from execution.failure_policy import FailureAction, FailureClass, FailurePolicy


def test_transient_read_failures_are_bounded():
    policy = FailurePolicy(max_read_retries=2)

    assert policy.decide(
        operation="get_order",
        failure_class=FailureClass.TRANSIENT,
        attempt=1,
    ).action is FailureAction.RETRY
    assert policy.decide(
        operation="get_order",
        failure_class=FailureClass.TRANSIENT,
        attempt=3,
    ).action is FailureAction.BLOCK


def test_unknown_state_requires_reconciliation():
    decision = FailurePolicy().decide(
        operation="get_order",
        failure_class=FailureClass.UNKNOWN,
        attempt=1,
    )

    assert decision.action is FailureAction.RECONCILE


def test_order_submission_is_never_retried():
    decision = FailurePolicy().decide(
        operation="submit_order",
        failure_class=FailureClass.TRANSIENT,
        attempt=1,
    )

    assert decision.action is FailureAction.RECONCILE
    assert decision.max_attempts == 0


def test_terminal_failures_block():
    decision = FailurePolicy().decide(
        operation="positions",
        failure_class=FailureClass.TERMINAL,
        attempt=1,
    )

    assert decision.action is FailureAction.BLOCK
