from execution.certification_matrix import (
    CERTIFICATION_ITEMS,
    CertificationEvidence,
    CertificationStatus,
    build_certification_report,
    readiness_gate_values,
)


def _all_pass():
    return {
        item.cert_id: CertificationEvidence(
            item.cert_id,
            CertificationStatus.PASS,
            evidence=(f"evidence:{item.cert_id}",),
        )
        for item in CERTIFICATION_ITEMS
    }


def test_certification_matrix_has_exactly_twelve_items():
    assert len(CERTIFICATION_ITEMS) == 12
    assert [item.cert_id for item in CERTIFICATION_ITEMS] == [
        f"CERT-{index:02d}" for index in range(1, 13)
    ]


def test_empty_evidence_is_not_certified():
    report = build_certification_report({})
    assert not report.passed
    assert len(report.missing) == 12


def test_all_explicit_pass_evidence_certifies():
    evidence = _all_pass()
    report = build_certification_report(evidence)
    assert report.passed
    assert report.failed == ()
    assert report.missing == ()


def test_any_non_pass_evidence_blocks_certification():
    evidence = _all_pass()
    evidence["CERT-12"] = CertificationEvidence(
        "CERT-12",
        CertificationStatus.UNVERIFIED,
        details=("provider evidence not collected",),
    )
    report = build_certification_report(evidence)
    assert not report.passed
    assert report.failed[0].cert_id == "CERT-12"


def test_gate_values_are_fail_closed_for_missing_evidence():
    values = readiness_gate_values({})
    assert len(values) == 12
    assert all(value is False for value in values.values())


def test_gate_values_only_promote_explicit_pass():
    evidence = _all_pass()
    evidence["CERT-12"] = CertificationEvidence(
        "CERT-12", CertificationStatus.UNVERIFIED
    )
    values = readiness_gate_values(evidence)
    assert values["provider_evidence_validated"] is False
    assert values["broker_contract_validated"] is True
    assert values["idempotency_validated"] is True


def test_unknown_certification_id_is_rejected():
    evidence = _all_pass()
    evidence["CERT-99"] = CertificationEvidence(
        "CERT-99", CertificationStatus.PASS
    )
    try:
        build_certification_report(evidence)
    except ValueError as exc:
        assert "CERT-99" in str(exc)
    else:
        raise AssertionError("unknown certification ID was accepted")
