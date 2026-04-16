import json

LOG_FILE = "memory/execution_log.json"


class ReliabilityManager:

    def __init__(self):
        self.data = {}

    def update(self, worker_name, success, confidence):
        if worker_name not in self.data:
            self.data[worker_name] = {
                "success": 0,
                "fail": 0,
                "avg_confidence": 0
            }

        if success:
            self.data[worker_name]["success"] += 1
        else:
            self.data[worker_name]["fail"] += 1

        # update confidence (simple moving avg)
        self.data[worker_name]["avg_confidence"] = (
            self.data[worker_name]["avg_confidence"] + confidence
        ) / 2

    def get_reliability(self, worker_name):
        data = self.data.get(worker_name)

        if not data:
            return 0.5

        total = data["success"] + data["fail"]
        if total == 0:
            return 0.5

        return round(data["success"] / total, 2)