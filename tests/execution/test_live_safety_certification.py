from execution.live_safety_certification import run_live_safety_certification


def test_live_safety_certification_passes():
    report = run_live_safety_certification()
    assert report.passed
    assert not report.failed


def test_live_safety_certification_has_expected_cases():
    report = run_live_safety_certification()
    assert [case.name for case in report.cases] == [
        "live_is_locked_by_default",
        "kill_switch_blocks_even_when_live_enabled",
        "stale_data_blocks_before_provider_routing",
        "invalid_data_quality_blocks",
        "closed_session_blocks",
        "provider_disabled_is_fail_closed",
        "enabled_provider_requires_injected_client",
    ]
