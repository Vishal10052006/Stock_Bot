import pytest

from execution.provider_evidence import ProviderEvidenceState
from execution.upstox_sandbox_restart_evidence import capture_sandbox_restart_evidence


def test_restart_rehydration_is_verified_without_duplicate_submission():
    result = capture_sandbox_restart_evidence(
        client_order_id="CID-1",
        pre_restart={"client_order_id": "CID-1", "status": "FILLED"},
        post_restart={"client_order_id": "CID-1", "status": "FILLED"},
        broker_order_id="OID-1",
        submission_count_before=1,
        submission_count_after=1,
    )
    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.recovered_status == "FILLED"


def test_missing_post_restart_state_is_unverified():
    result = capture_sandbox_restart_evidence(
        client_order_id="CID-1",
        pre_restart={"client_order_id": "CID-1", "status": "OPEN"},
        post_restart=None,
        broker_order_id="OID-1",
        submission_count_before=1,
        submission_count_after=1,
    )
    assert result.observation.state is ProviderEvidenceState.UNVERIFIED


def test_duplicate_submission_fails():
    result = capture_sandbox_restart_evidence(
        client_order_id="CID-1",
        pre_restart={"client_order_id": "CID-1", "status": "OPEN"},
        post_restart={"client_order_id": "CID-1", "status": "OPEN"},
        broker_order_id="OID-1",
        submission_count_before=1,
        submission_count_after=2,
    )
    assert result.observation.state is ProviderEvidenceState.FAILED


def test_identity_mismatch_fails():
    result = capture_sandbox_restart_evidence(
        client_order_id="CID-1",
        pre_restart={"client_order_id": "CID-1", "status": "OPEN"},
        post_restart={"client_order_id": "CID-2", "status": "OPEN"},
        broker_order_id="OID-1",
        submission_count_before=1,
        submission_count_after=1,
    )
    assert result.observation.state is ProviderEvidenceState.FAILED


def test_unknown_state_is_not_claimed_as_verified():
    result = capture_sandbox_restart_evidence(
        client_order_id="CID-1",
        pre_restart={"client_order_id": "CID-1", "status": "UNKNOWN"},
        post_restart={"client_order_id": "CID-1", "status": "UNKNOWN"},
        broker_order_id="OID-1",
        submission_count_before=1,
        submission_count_after=1,
    )
    assert result.observation.state is ProviderEvidenceState.UNVERIFIED


def test_invalid_status_is_rejected():
    with pytest.raises(ValueError):
        capture_sandbox_restart_evidence(
            client_order_id="CID-1",
            pre_restart={"client_order_id": "CID-1"},
            post_restart={"client_order_id": "CID-1", "status": "NOT_A_STATE"},
            broker_order_id="OID-1",
            submission_count_before=1,
            submission_count_after=1,
        )
