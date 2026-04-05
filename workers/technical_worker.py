from workers.base_worker import BaseWorker
import random

class TechnicalWorker(BaseWorker):
    name = "technical_worker"

    def execute(self, task):
        print("[TechnicalWorker] Analyzing indicators...")

        return {
            "signal": random.choice(["BUY", "SELL", "HOLD"]),
            "confidence": random.uniform(0.5, 0.9),
            "success": True
        }