"""Regression tests for the AUTO control-plane primitives."""

from datetime import datetime, timezone

from automation.contracts import AutomationMode, RunStatus, Stage
from automation.gates import AutomationGateError, require_causal_timestamp
from automation.orchestrator import AutomationOrchestrator


DECISION = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def test_run_context_is_causal_and_succeeds_without_handlers() -> None:
    """Missing handlers become explicit skips, not fabricated engine success."""
    result = AutomationOrchestrator().run(
        symbol="INFY",
        decision_timestamp=DECISION,
        mode=AutomationMode.PAPER,
    )

    assert result.run.status is RunStatus.SUCCEEDED
    assert result.run.symbol == "INFY"
    assert result.run.idempotency_key


def test_unconfigured_stages_are_explicitly_skipped() -> None:
    """Every absent integration seam emits a visible skip event."""
    result = AutomationOrchestrator().run(
        symbol="INFY",
        decision_timestamp=DECISION,
    )

    skipped = [
        event for event in result.events if event.event_type == "STAGE_SKIPPED"
    ]
    assert len(skipped) == len(AutomationOrchestrator.ORDER)


def test_future_observation_is_rejected() -> None:
    """Causal boundaries must reject future information."""
    future = datetime(2026, 9, 29, 12, 5, tzinfo=timezone.utc)

    try:
        require_causal_timestamp(DECISION, future)
    except AutomationGateError:
        return

    raise AssertionError("future observation should be rejected")


def test_execution_is_blocked_outside_paper_mode() -> None:
    """Shadow/readiness runs may never reach an execution handler."""
    called = {"value": False}

    def execution_handler(_run, _payload):
        called["value"] = True
        return {"submitted": True}

    result = AutomationOrchestrator(
        handlers={Stage.EXECUTION: execution_handler}
    ).run(
        symbol="INFY",
        decision_timestamp=DECISION,
        mode=AutomationMode.SHADOW,
    )

    assert result.run.status is RunStatus.FAILED
    assert not called["value"]
