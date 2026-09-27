import pytest

from execution.upstox_operational_certification import UpstoxOperationalCertification


def complete_certification():
    return UpstoxOperationalCertification(
        adapter_contract=True,
        sandbox_authentication=True,
        sandbox_order_lifecycle=True,
        provider_error_handling=True,
        reconciliation_boundary=True,
        ci_validated=True,
        live_execution_locked=True,
    )


def test_complete_software_certification_passes():
    certification = complete_certification()
    assert certification.software_complete
    certification.assert_safe()


def test_missing_gate_blocks_certification():
    certification = UpstoxOperationalCertification(
        adapter_contract=True,
        sandbox_authentication=True,
        sandbox_order_lifecycle=True,
        provider_error_handling=False,
        reconciliation_boundary=True,
        ci_validated=True,
    )
    assert not certification.software_complete
    with pytest.raises(ValueError, match="incomplete"):
        certification.assert_safe()


def test_live_unlock_is_never_part_of_certification():
    certification = complete_certification()
    object.__setattr__(certification, "live_execution_locked", False)
    with pytest.raises(ValueError, match="unlock live execution"):
        certification.assert_safe()
