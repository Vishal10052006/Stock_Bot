from execution.upstox_readiness import (
    UpstoxCapabilityEvidence,
    UpstoxEvidenceState,
    build_position_reconciliation_evidence,
    build_upstox_readiness_attestation,
)
from execution.engine import PositionSnapshot


def test_empty_readiness_attestation_fails_closed():
    try:
        build_upstox_readiness_attestation(())
    except ValueError:
        return
    raise AssertionError("empty provider evidence must fail closed")


def test_unverified_provider_capability_blocks_attestation():
    report = build_upstox_readiness_attestation(
        (
            UpstoxCapabilityEvidence(
                "position_reconciliation",
                UpstoxEvidenceState.UNVERIFIED,
                "production",
                "no real provider observation recorded",
            ),
        )
    )
    assert report.blocked
    assert not report.verified


def test_all_verified_capabilities_produce_verified_attestation():
    report = build_upstox_readiness_attestation(
        (
            UpstoxCapabilityEvidence(
                "authentication",
                UpstoxEvidenceState.VERIFIED,
                "sandbox",
                "authenticated provider request observed",
            ),
            UpstoxCapabilityEvidence(
                "cancellation",
                UpstoxEvidenceState.VERIFIED,
                "sandbox",
                "cancel acknowledgement observed",
            ),
        )
    )
    assert not report.blocked
    assert report.verified


def test_attestation_fingerprint_is_deterministic():
    capabilities = (
        UpstoxCapabilityEvidence(
            "authentication",
            UpstoxEvidenceState.VERIFIED,
            "sandbox",
            "observed",
        ),
    )
    first = build_upstox_readiness_attestation(capabilities)
    second = build_upstox_readiness_attestation(capabilities)
    assert first.evidence_fingerprint == second.evidence_fingerprint


def test_position_reconciliation_evidence_is_non_authorizing():
    local = (PositionSnapshot("ITC", 10.0, 450.0),)
    broker = (PositionSnapshot("ITC", 10.0, 450.0),)
    report = build_position_reconciliation_evidence(local, broker)
    assert report.safe


def test_missing_position_provider_evidence_blocks():
    local = (PositionSnapshot("ITC", 10.0, 450.0),)
    report = build_position_reconciliation_evidence(local, None)
    assert report.status == "BLOCKED"
    assert not report.safe
