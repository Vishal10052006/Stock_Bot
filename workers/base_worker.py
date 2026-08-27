"""
Stock Bot — Base Worker Contract

Defines the interface that every executable worker must implement.
"""


class BaseWorker:
    """Base contract for workers used by the execution layer."""

    name = "base_worker"
    capabilities = []

    def execute(self, task):
        """Execute a task and return the worker result."""
        raise NotImplementedError
