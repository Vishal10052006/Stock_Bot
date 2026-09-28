from execution.upstox_certification import (
    UpstoxFailureClass,
    assert_unknown_requires_reconciliation,
    classify_upstox_error,
    validate_rejection_state,
)


def test_authentication_is_non_retryable():
    error = classify_upstox_error(http_status=401, code="401", message="unauthorized")
    assert error.failure_class is UpstoxFailureClass.AUTHENTICATION
    assert not error.retryable
    assert not error.requires_reconciliation


def test_rate_limit_is_retryable_without_order_ambiguity():
    error = classify_upstox_error(http_status=429, message="too many requests")
    assert error.failure_class is UpstoxFailureClass.RATE_LIMIT
    assert error.retryable
    assert not error.requires_reconciliation


def test_network_failure_requires_reconciliation_and_no_blind_retry():
    error = classify_upstox_error(message="request timeout")
    assert error.failure_class is UpstoxFailureClass.NETWORK
    assert not error.retryable
    assert error.requires_reconciliation
    assert_unknown_requires_reconciliation(error)


def test_provider_failure_requires_reconciliation():
    error = classify_upstox_error(http_status=503, message="service unavailable")
    assert error.failure_class is UpstoxFailureClass.PROVIDER_UNAVAILABLE
    assert error.requires_reconciliation


def test_rejection_preserves_reason():
    validate_rejection_state(status="rejected", reason="instrument blocked")


def test_empty_rejection_reason_fails_closed():
    try:
        validate_rejection_state(status="rejected", reason="")
    except ValueError:
        return
    raise AssertionError("empty broker rejection reason must fail closed")


def test_unknown_is_fail_closed():
    error = classify_upstox_error(message="unrecognized provider response")
    assert error.failure_class is UpstoxFailureClass.UNKNOWN
    assert not error.retryable
    assert error.requires_reconciliation
