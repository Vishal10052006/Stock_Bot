from execution.provider_evidence import ProviderEvidenceState
from execution.upstox_sandbox_evidence import capture_sandbox_order_state_evidence


def test_capture_sandbox_order_state_evidence_requires_broker_identity():
    try:
        capture_sandbox_order_state_evidence(
            request={"tag": "SB-1"},
            placed_response={"status": "success", "data": {}},
            lookup_response=None,
            cancelled_response=None,
        )
    except ValueError:
        return
    raise AssertionError("missing broker order identity must fail closed")


def test_capture_sandbox_order_state_evidence_marks_lookup_match_verified():
    result = capture_sandbox_order_state_evidence(
        request={"tag": "SB-1"},
        placed_response={"status": "success", "data": {"order_id": "OID-1", "tag": "SB-1"}},
        lookup_response={
            "status": "success",
            "data": {"order_id": "OID-1", "tag": "SB-1", "status": "cancelled"},
        },
        cancelled_response={
            "status": "success",
            "data": {"order_id": "OID-1", "status": "cancelled"},
        },
    )
    assert result.broker_order_id == "OID-1"
    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.observation.operation == "place → lookup → cancel"


def test_capture_sandbox_order_state_evidence_detects_identity_mismatch():
    result = capture_sandbox_order_state_evidence(
        request={"tag": "SB-1"},
        placed_response={"status": "success", "data": {"order_id": "OID-1", "tag": "SB-1"}},
        lookup_response={"status": "success", "data": {"order_id": "OID-2", "tag": "SB-1"}},
        cancelled_response=None,
    )
    assert result.observation.state is ProviderEvidenceState.FAILED
    assert "identity" in result.observation.detail


def test_capture_sandbox_order_state_evidence_requires_observed_lookup():
    result = capture_sandbox_order_state_evidence(
        request={"tag": "SB-1"},
        placed_response={"status": "success", "data": {"order_id": "OID-1", "tag": "SB-1"}},
        lookup_response=None,
        cancelled_response=None,
    )
    assert result.observation.state is ProviderEvidenceState.UNVERIFIED
