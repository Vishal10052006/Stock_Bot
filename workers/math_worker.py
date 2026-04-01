from workers.base_worker import BaseWorker

class MathWorker(BaseWorker):
    def __init__(self):
        self.name = "math_worker"

    def execute(self, task):
        print(f"[MathWorker] Processing: {task}")

        return {
            "success": True,
            "confidence": 0.7,
            "output": "Math result"
        }