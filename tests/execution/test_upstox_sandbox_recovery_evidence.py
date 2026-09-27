import pytest

from execution.provider_evidence import ProviderEvidenceState
from execution.upstox_certification import UpstoxFailureClass
from execution.upstox_sandbox_recovery_evidence import (
    capture_sandbox_timeout_recovery_evidence,
)


def test_timeout_requires_reconciliation():
    result = capture_sandbox_timeout_recovery_evidence(
        failure={"error_type": "TimeoutError", "message": "request timed out"}
    )

    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.failure_class is UpstoxFailureClass.NETWORK
    assert result.requires_reconciliation is True


def test_network_failure_requires_reconciliation():
    result = capture_sandbox_timeout_recovery_evidence(
        failure={"message": "connection reset by peer"}
    )

    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.failure_class is UpstoxFailureClass.NETWORK
    assert result.requires_reconciliation is True


def test_provider_5xx_requires_reconciliation():
    result = capture_sandbox_timeout_recovery_evidence(
        failure={"status_code": 503, "message": "service unavailable"}
    )

    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.failure_class is UpstoxFailureClass.PROVIDER_UNAVAILABLE
    assert result.requires_reconciliation is True


def test_non_ambiguous_failure_does_not_claim_timeout_recovery():
    result = capture_sandbox_timeout_recovery_evidence(
        failure={"status_code": 401, "message": "invalid token"}
    )

    assert result.observation.state is ProviderEvidenceState.UNVERIFIED
    assert result.failure_class is UpstoxFailureClass.AUTHENTICATION
    assert result.requires_reconciliation is False


@pytest.mark.parametrize(
    "failure",
    [
        {},
        {"message": ""},
        {"error_type": ""},
        {"status_code": "not-a-number", "message": "timeout"},
    ],
)
def test_malformed_failure_is_rejected(failure):
    with pytest.raises(ValueError):
        capture_sandbox_timeout_recovery_evidence(failure=failure)
