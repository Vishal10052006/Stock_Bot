def execute(self, task):
    print("[StrategyWorker] Combining signals...")

    return {
        "signal": "BUY",
        "confidence": 0.85,
        "success": True
    }