"""Execution boundary for worker-level analysis.

This module is intentionally NOT the broker execution layer.

Its responsibility is limited to invoking a registered analysis worker
and recording the worker invocation. Financial order execution belongs
to the future trading execution boundary and must require a validated
risk-approved trading decision.
"""

from __future__ import annotations

from typing import Any

from workers.worker_loader import WorkerLoader
from workers.worker_registry import WorkerRegistry


class ExecutionEngine:
    """Execute registered analysis workers safely.

    This legacy-compatible adapter does not:
        - plan generic commands
        - route tasks
        - score outputs with a critic
        - manufacture trading confidence
        - generate trading decisions
        - perform reinforcement learning
        - place broker orders
    """

    def __init__(self) -> None:
        self.registry = WorkerRegistry()
        WorkerLoader(self.registry).load_workers()

    async def run(
        self,
        command: Any,
        worker_name: str,
    ) -> list[dict[str, Any]]:
        """Execute exactly one registered worker.

        No planning, critic scoring, reinforcement learning, or
        financial order execution occurs here.
        """
        result = self.execute(command, worker_name)
        return [result]

    def execute(
        self,
        task: Any,
        worker_name: str,
    ) -> dict[str, Any]:
        """Invoke one registered worker and return its result."""
        worker = self.registry.get_worker(worker_name)

        result = worker.execute(task)

        if not isinstance(result, dict):
            raise TypeError(
                f"Worker '{worker_name}' must return a dict, "
                f"got {type(result).__name__}"
            )

        return result
