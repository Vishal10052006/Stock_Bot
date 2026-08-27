"""
Stock Bot — Strategy Worker

Generates a strategy using historical execution outcomes stored in
long-term memory.
"""

from workers.base_worker import BaseWorker
from memory.memory_manager import MemoryManager


class StrategyWorker(BaseWorker):
    """Worker responsible for strategy generation from execution history."""

    name = "strategy_worker"

    def __init__(self):
        """Initialize the strategy worker and its memory manager."""
        self.memory_manager = MemoryManager()

    def execute(self, task):
        """Generate a strategy and return the standard worker result contract."""

        print("[StrategyWorker] Generating strategy...")

        # Load historical execution outcomes for worker-performance analysis.
        memory = self.memory_manager.load_memory()

        executions = [
            item
            for item in memory
            if item.get("type") == "execution"
        ]

        performance = {}

        # Calculate historical success rate for each worker.
        for item in executions:
            worker = item.get("worker")
            result = item.get("result")

            if worker not in performance:
                performance[worker] = {
                    "success": 0,
                    "total": 0,
                }

            performance[worker]["total"] += 1

            if result == "SUCCESS":
                performance[worker]["success"] += 1

        best_worker = None
        best_score = 0.0

        # Select the worker with the highest historical success rate.
        for worker, stats in performance.items():
            score = stats["success"] / stats["total"]

            if score > best_score:
                best_score = score
                best_worker = worker

        # Return the standard worker execution contract.
        return {
            "best_worker": best_worker or "strategy_worker",
            "confidence": 0.8,
            "success": True,
        }
