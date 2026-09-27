import pytest

from execution.provider_evidence import ProviderEvidenceState
from execution.upstox_sandbox_rate_limit_evidence import (
    bounded_rate_limit_backoff,
    capture_sandbox_rate_limit_evidence,
)


def test_explicit_429_is_verified():
    result = capture_sandbox_rate_limit_evidence(
        response={
            "status_code": 429,
            "code": "UDAPI100060",
            "message": "rate limit exceeded",
        },
        retry_after_seconds=2,
    )

    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.http_status == 429
    assert result.retry_after_seconds == 2


def test_retry_after_header_is_captured():
    result = capture_sandbox_rate_limit_evidence(
        response={
            "status_code": 429,
            "headers": {"Retry-After": "5"},
        }
    )

    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.retry_after_seconds == 5


def test_non_429_does_not_claim_rate_limit():
    result = capture_sandbox_rate_limit_evidence(
        response={"status_code": 500, "message": "provider unavailable"}
    )

    assert result.observation.state is ProviderEvidenceState.UNVERIFIED


def test_bounded_backoff_is_deterministic_and_capped():
    assert bounded_rate_limit_backoff(attempt=0) == 1.0
    assert bounded_rate_limit_backoff(attempt=3) == 8.0
    assert bounded_rate_limit_backoff(attempt=10) == 30.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"attempt": -1},
        {"attempt": 0, "base_seconds": 0},
        {"attempt": 0, "base_seconds": float("nan")},
        {"attempt": 0, "cap_seconds": 0},
        {"attempt": 0, "base_seconds": 31, "cap_seconds": 30},
    ],
)
def test_bounded_backoff_rejects_invalid_policy(kwargs):
    with pytest.raises(ValueError):
        bounded_rate_limit_backoff(**kwargs)


def test_invalid_retry_after_is_rejected():
    with pytest.raises(ValueError):
        capture_sandbox_rate_limit_evidence(
            response={"status_code": 429},
            retry_after_seconds=-1,
        )
