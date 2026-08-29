"""
Stock Bot — Worker Registry

Maintains the runtime registry of executable workers.

The registry stores worker instances and exposes them to the
decision and execution layers.
"""


class WorkerRegistry:
    """Registry for executable worker instances."""

    def __init__(self):
        """Initialize an empty worker registry."""

        self.workers = {}

    def register(self, worker):
        """Register a worker using its unique name."""

        self.workers[worker.name] = worker

    def all_workers(self):
        """
        Return all registered worker instances.

        The decision layer needs worker objects so it can access
        attributes such as name and capabilities.
        """

        return list(self.workers.values())

    def as_mapping(self):
        """
        Return registered workers as a name-to-instance mapping.

        This adapter allows the execution layer to resolve workers
        by their canonical registry names.
        """

        return dict(self.workers)

    def get_worker(self, worker_name):
        """
        Return a worker by name.

        Raises:
            ValueError: If the requested worker is not registered.
        """

        worker = self.workers.get(worker_name)

        if worker is None:
            raise ValueError(
                f"Worker '{worker_name}' not found"
            )

        return worker
