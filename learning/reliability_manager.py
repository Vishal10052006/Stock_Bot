"""
Stock Bot — Reliability Manager

Tracks worker execution success rates and confidence.
"""


class ReliabilityManager:
    """Maintain reliability statistics for each worker."""

    def __init__(self):
        """Initialize empty reliability statistics."""
        self.data = {}

    def update(self, worker_name, success, confidence):
        """Record one worker execution outcome."""

        if worker_name not in self.data:
            self.data[worker_name] = {
                "success": 0,
                "fail": 0,
                "avg_confidence": 0.0,
            }

        if success:
            self.data[worker_name]["success"] += 1
        else:
            self.data[worker_name]["fail"] += 1

        # Update the running confidence estimate.
        previous = self.data[worker_name]["avg_confidence"]

        self.data[worker_name]["avg_confidence"] = (
            previous + confidence
        ) / 2

    def get_reliability(self, worker_name):
        """Return the historical success rate for a worker."""

        data = self.data.get(worker_name)

        if not data:
            return 0.5

        total = data["success"] + data["fail"]

        if total == 0:
            return 0.5

        return round(data["success"] / total, 2)
