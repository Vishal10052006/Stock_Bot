"""
Stock Bot — Execution Engine

Phase 1 execution boundary.

Responsibilities:
    1. Resolve a registered worker.
    2. Execute the worker task.
    3. Normalize the worker result contract.
    4. Record reliability statistics.
    5. Persist the execution outcome.

Decision-making, planning, critic evaluation, and orchestration
belong outside this layer.
"""

import inspect

from execution.executor import Executor
from workers.worker_loader import WorkerLoader
from workers.worker_registry import WorkerRegistry


class ExecutionEngine:
    """Execute one selected worker and record its outcome."""

    def __init__(
        self,
        trust_manager,
        memory_manager,
        learning_engine,
        reinforcement_engine,
        reliability_manager,
    ):
        """Initialize execution dependencies and load workers."""

        self.trust_manager = trust_manager
        self.memory_manager = memory_manager
        self.learning_engine = learning_engine
        self.reinforcement_engine = reinforcement_engine
        self.reliability_manager = reliability_manager

        # Worker execution infrastructure.
        self.executor = Executor()
        self.registry = WorkerRegistry()

        # Load all configured workers into the runtime registry.
        loader = WorkerLoader(self.registry)
        loader.load_workers()

    async def run(self, command, worker_name):
        """
        Execute a selected worker.

        Args:
            command: Task passed to the worker.
            worker_name: Registered worker name.

        Returns:
            Standard worker result dictionary.

        Raises:
            ValueError: If the worker does not exist.
        """

        worker = self.registry.get_worker(worker_name)

        try:
            # Execute through the worker directly. Executor remains
            # available for multi-worker execution in future phases.
            result = worker.execute(command)

            # Support asynchronous workers without changing the
            # execution-engine public contract.
            if inspect.isawaitable(result):
                result = await result

        except Exception:
            # Convert execution failures into the standard result
            # contract so downstream learning remains deterministic.
            result = {
                "success": False,
                "confidence": 0.0,
                "worker": worker.name,
            }

        result = self._normalize_result(
            result=result,
            worker_name=worker.name,
        )

        self._record_outcome(
            command=command,
            worker_name=worker.name,
            result=result,
        )

        return result

    @staticmethod
    def _normalize_result(result, worker_name):
        """
        Normalize worker output to the Phase 1 result contract.

        Required fields:
            success: bool
            confidence: float
        """

        if not isinstance(result, dict):
            return {
                "success": True,
                "confidence": 1.0,
                "worker": worker_name,
                "output": result,
            }

        normalized = dict(result)

        normalized.setdefault("success", True)
        normalized.setdefault("confidence", 1.0)
        normalized.setdefault("worker", worker_name)

        # Keep confidence bounded for downstream scoring.
        try:
            normalized["confidence"] = max(
                0.0,
                min(1.0, float(normalized["confidence"])),
            )
        except (TypeError, ValueError):
            normalized["confidence"] = 0.0

        normalized["success"] = bool(normalized["success"])

        return normalized

    def _record_outcome(self, command, worker_name, result):
        """Record reliability and persistent execution history."""

        success = result["success"]
        confidence = result["confidence"]

        # Update in-memory reliability statistics.
        self.reliability_manager.update(
            worker_name,
            success,
            confidence,
        )

        # Persist a standardized execution record for future learning.
        self.memory_manager.add_memory(
            {
                "type": "execution",
                "worker": worker_name,
                "task": command,
                "result": "SUCCESS" if success else "FAILED",
                "confidence": confidence,
            }
        )
