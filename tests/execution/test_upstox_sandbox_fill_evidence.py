from execution.provider_evidence import ProviderEvidenceState
from execution.upstox_sandbox_fill_evidence import capture_sandbox_fill_evidence


def test_missing_fill_state_is_unverified():
    result = capture_sandbox_fill_evidence(
        placed_response={"data": {"order_id": "OID-1"}},
        state_response=None,
    )
    assert result.broker_order_id == "OID-1"
    assert result.observation.state is ProviderEvidenceState.UNVERIFIED


def test_valid_partial_fill_is_verified():
    result = capture_sandbox_fill_evidence(
        placed_response={"data": {"order_id": "OID-1"}},
        state_response={
            "status": "success",
            "data": {
                "order_id": "OID-1",
                "quantity": 100,
                "filled_quantity": 40,
                "status": "partially filled",
            },
        },
    )
    assert result.observation.state is ProviderEvidenceState.VERIFIED
    assert result.filled_quantity == 40


def test_partial_fill_identity_mismatch_fails():
    result = capture_sandbox_fill_evidence(
        placed_response={"data": {"order_id": "OID-1"}},
        state_response={
            "data": {
                "order_id": "OID-2",
                "quantity": 100,
                "filled_quantity": 40,
                "status": "partially filled",
            }
        },
    )
    assert result.observation.state is ProviderEvidenceState.FAILED


def test_invalid_partial_fill_quantity_fails():
    result = capture_sandbox_fill_evidence(
        placed_response={"data": {"order_id": "OID-1"}},
        state_response={
            "data": {
                "order_id": "OID-1",
                "quantity": 100,
                "filled_quantity": 100,
                "status": "partially filled",
            }
        },
    )
    assert result.observation.state is ProviderEvidenceState.FAILED


def test_filled_state_does_not_claim_partial_fill():
    result = capture_sandbox_fill_evidence(
        placed_response={"data": {"order_id": "OID-1"}},
        state_response={
            "data": {
                "order_id": "OID-1",
                "quantity": 100,
                "filled_quantity": 100,
                "status": "complete",
            }
        },
    )
    assert result.observation.state is ProviderEvidenceState.UNVERIFIED
