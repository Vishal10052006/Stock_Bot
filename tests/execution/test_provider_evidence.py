import pytest

from execution.provider_evidence import (
    ProviderEvidenceObservation,
    ProviderEvidenceState,
    build_provider_evidence_report,
    build_upstox_controlled_evidence_plan,
    evidence_payload,
)


def test_controlled_upstox_plan_is_fail_closed():
    report = build_upstox_controlled_evidence_plan()
    assert report.provider == "upstox"
    assert report.blocked
    assert report.observations
    assert all(item.state is ProviderEvidenceState.UNVERIFIED for item in report.observations)


def test_provider_evidence_report_rejects_empty_observations():
    with pytest.raises(ValueError, match="at least one"):
        build_provider_evidence_report("upstox", ())


def test_provider_evidence_report_rejects_empty_fields():
    with pytest.raises(ValueError, match="operation"):
        build_provider_evidence_report(
            "upstox",
            (
                ProviderEvidenceObservation(
                    "partial_fill",
                    "sandbox",
                    "",
                    ProviderEvidenceState.UNVERIFIED,
                    "not observed",
                ),
            ),
        )


def test_evidence_payload_preserves_observed_state():
    item = evidence_payload(
        {
            "capability": "cancellation",
            "environment": "sandbox",
            "operation": "cancel acknowledgement",
            "state": "VERIFIED",
            "detail": "provider response observed",
        }
    )
    assert item.capability == "cancellation"
    assert item.environment == "sandbox"
    assert item.operation == "cancel acknowledgement"
    assert item.state is ProviderEvidenceState.VERIFIED


def test_verified_only_report_is_not_blocked():
    report = build_provider_evidence_report(
        "upstox",
        (
            ProviderEvidenceObservation(
                "authentication",
                "sandbox",
                "authenticated request",
                ProviderEvidenceState.VERIFIED,
                "observed",
            ),
        ),
    )
    assert not report.blocked
