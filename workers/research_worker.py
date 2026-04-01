from workers.base_worker import BaseWorker
import asyncio

class ResearchWorker(BaseWorker):
    def __init__(self):
        self.name = "research_worker"

    def execute(self, task):
        print(f"[Research Worker] Processing: {task}")

        return {
            "success": True,
            "confidence": 0.8,
            "output": "Research result"
        }