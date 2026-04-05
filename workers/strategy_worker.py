from workers.base_worker import BaseWorker
from core.memory_manager import MemoryManager

class StrategyWorker(BaseWorker):
    name = "strategy_worker"

    def __init__(self):
        self.memory_manager = MemoryManager()

    def execute(self, task):
        print("[StrategyWorker] Generating strategy...")

        memory = self.memory_manager.load_memory()

        executions = [
            m for m in memory
            if m.get("type") == "execution"
        ]

        performance = {}

        for m in executions:
            worker = m.get("worker")
            result = m.get("result")

            if worker not in performance:
                performance[worker] = {"success": 0, "total": 0}

            performance[worker]["total"] += 1

            if result == "SUCCESS":
                performance[worker]["success"] += 1

        best_worker = None
        best_score = 0

        for worker, stats in performance.items():
            score = stats["success"] / stats["total"]

            if score > best_score:
                best_score = score
                best_worker = worker

        return {
            "best_worker": "strategy_worker",
            "confidence": 0.8
        }