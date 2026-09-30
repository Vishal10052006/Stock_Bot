"""Automation coordinator for existing STOCK_BOT engines.

This control-plane module deliberately contains no prediction, strategy,
risk-sizing, broker, or model-promotion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .contracts import (
    AutomationMode,
    AutomationResult,
    RunContext,
    RunStatus,
    Stage,
    StageEvent,
)
from .event_bus import EventBus
from .gates import AutomationGateError
from .state_store import RunStateStore


@dataclass(frozen=True, slots=True)
class PipelineHandlers:
    """Dependency-injected handlers owned by existing STOCK_BOT layers."""

    handlers: Mapping[Stage, Callable[[RunContext, Mapping[str, Any]], Any]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "handlers", dict(self.handlers))


class AutomationOrchestrator:
    """Execute the canonical pipeline as a fail-closed stateful graph."""

    ORDER = (
        Stage.DATA,
        Stage.RESEARCH,
        Stage.MARKET,
        Stage.ANALYSIS,
        Stage.PREDICTION,
        Stage.STRATEGY,
        Stage.RISK,
        Stage.SAFETY,
        Stage.EXECUTION,
        Stage.MONITORING,
    )

    def __init__(
        self,
        *,
        handlers: Mapping[Stage, Callable[[RunContext, Mapping[str, Any]], Any]] | None = None,
        state_store: RunStateStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.handlers = dict(handlers or {})
        self.state_store = state_store or RunStateStore()
        self.event_bus = event_bus or EventBus()

    def _emit(
        self,
        run: RunContext,
        stage: Stage,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
    ) -> StageEvent:
        """Persist and publish one stage event."""
        event = StageEvent(
            run_id=run.run_id,
            stage=stage,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            payload=dict(payload or {}),
        )
        self.state_store.append(event)
        self.event_bus.publish(event)
        return event

    def run(
        self,
        *,
        symbol: str,
        decision_timestamp: datetime,
        mode: AutomationMode = AutomationMode.PAPER,
        initial_inputs: Mapping[str, Any] | None = None,
        versions: Mapping[str, str] | None = None,
    ) -> AutomationResult:
        """Run configured stages in canonical order."""
        if decision_timestamp.tzinfo is None:
            raise ValueError("decision_timestamp must be timezone-aware")

        run = RunContext.create(
            symbol=symbol,
            decision_timestamp=decision_timestamp,
            mode=mode,
            versions=versions,
        )
        record = self.state_store.create(run)

        if record.context.run_id != run.run_id:
            return AutomationResult(
                run=record.context.with_status(RunStatus.REJECTED),
                events=tuple(record.events),
                error="IDEMPOTENT_DUPLICATE",
            )

        run = run.with_status(RunStatus.RUNNING)
        self.state_store.update_context(run)

        outputs: dict[Stage, Any] = {}
        events: list[StageEvent] = []
        payload: dict[str, Any] = dict(initial_inputs or {})

        try:
            for stage in self.ORDER:
                handler = self.handlers.get(stage)

                if handler is None:
                    events.append(
                        self._emit(
                            run,
                            stage,
                            "STAGE_SKIPPED",
                            {"reason": "handler_not_configured"},
                        )
                    )
                    continue

                if stage is Stage.EXECUTION and mode is not AutomationMode.PAPER:
                    raise AutomationGateError(
                        "execution stage is only available in paper mode"
                    )

                events.append(self._emit(run, stage, "STAGE_STARTED"))
                result = handler(run, payload)
                outputs[stage] = result
                payload[stage.value.lower()] = result
                events.append(self._emit(run, stage, "STAGE_COMPLETED"))

            run = run.with_status(RunStatus.SUCCEEDED)
            self.state_store.update_context(run)
            return AutomationResult(
                run=run,
                events=tuple(events),
                outputs=outputs,
            )
        except Exception as exc:
            run = run.with_status(RunStatus.FAILED)
            self.state_store.update_context(run)
            events.append(
                self._emit(
                    run,
                    Stage.MONITORING,
                    "RUN_FAILED",
                    {"error": str(exc)},
                )
            )
            return AutomationResult(
                run=run,
                events=tuple(events),
                outputs=outputs,
                error=str(exc),
            )
