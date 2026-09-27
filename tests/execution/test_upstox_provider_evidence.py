from execution.provider_evidence import (
    ProviderEvidenceObservation,
    ProviderEvidenceState,
)
from execution.upstox_provider_evidence import build_upstox_provider_evidence_bundle


def test_provider_evidence_bundle_preserves_observations_and_blocks_unverified():
    observations = (
        ProviderEvidenceObservation(
            "order_history",
            "sandbox",
            "place -> lookup",
            ProviderEvidenceState.VERIFIED,
            "broker lookup matched placement identity",
        ),
        ProviderEvidenceObservation(
            "position_reconciliation",
            "production",
            "read-only positions observation",
            ProviderEvidenceState.UNVERIFIED,
            "provider evidence not captured",
        ),
    )

    report, readiness = build_upstox_provider_evidence_bundle(observations)

    assert report.provider == "upstox"
    assert report.observations == observations
    assert report.blocked
    assert readiness.blocked
    assert not readiness.verified
    assert [item.capability for item in readiness.capabilities] == [
        "order_history",
        "position_reconciliation",
    ]


def test_provider_evidence_bundle_is_deterministic():
    observations = (
        ProviderEvidenceObservation(
            "authentication",
            "sandbox",
            "authenticated request",
            ProviderEvidenceState.VERIFIED,
            "observed",
        ),
    )

    first_report, first_readiness = build_upstox_provider_evidence_bundle(observations)
    second_report, second_readiness = build_upstox_provider_evidence_bundle(observations)

    assert first_report == second_report
    assert first_readiness.evidence_fingerprint == second_readiness.evidence_fingerprint
    assert first_readiness.verified


def test_provider_evidence_bundle_rejects_empty_observations():
    try:
        build_upstox_provider_evidence_bundle(())
    except ValueError:
        return
    raise AssertionError("empty provider evidence must fail closed")
