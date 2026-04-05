from workers.base_worker import BaseWorker
import random

class SentimentWorker(BaseWorker):
    name = "sentiment_worker"

    def execute(self, task):
        print("[SentimentWorker] Analyzing news sentiment...")

        return {
            "signal": random.choice(["BUY", "SELL", "HOLD"]),
            "confidence": random.uniform(0.4, 0.85),
            "success": True
        }