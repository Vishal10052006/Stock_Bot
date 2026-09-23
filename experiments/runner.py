"""Deterministic orchestration boundary for reproducible experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .definition import ExperimentDefinition
from .record import ExperimentRecord


@dataclass(frozen=True, slots=True)
class ExperimentExecution:
    """Completed experiment paired with its exact definition."""

    definition: ExperimentDefinition
    record: ExperimentRecord

    def __post_init__(self) -> None:
        """Fail closed if a result belongs to another experiment."""
        expected = self.definition.fingerprint()
        if self.record.definition_fingerprint != expected:
            raise ValueError(
                "experiment record fingerprint does not match definition"
            )


class ExperimentRunner:
    """Run one explicitly defined experiment through a supplied executor.

    The runner deliberately does not invent a dataset, model, backtest, or
    evaluation policy. The executor receives the frozen definition and must
    return an ExperimentRecord bound to that definition. This keeps execution
    mechanics separate from research policy and prevents hidden configuration.
    """

    def __init__(self, definition: ExperimentDefinition) -> None:
        if not isinstance(definition, ExperimentDefinition):
            raise TypeError(
                "definition must be an ExperimentDefinition"
            )
        self.definition = definition

    def run(
        self,
        executor: Callable[[ExperimentDefinition], ExperimentRecord],
    ) -> ExperimentExecution:
        """Execute one frozen experiment and validate its result identity."""
        if not callable(executor):
            raise TypeError("executor must be callable")

        record = executor(self.definition)

        if not isinstance(record, ExperimentRecord):
            raise TypeError(
                "experiment executor must return an ExperimentRecord"
            )

        return ExperimentExecution(
            definition=self.definition,
            record=record,
        )
