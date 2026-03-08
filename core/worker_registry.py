class WorkerRegistry:

    def __init__(self):
        self._workers = {}

    def register(self, name: str, worker):
        self._workers[name] = worker

    def get_worker(self, intent: str):
        return self._workers.get(intent)

    def all_workers(self):
        return self._workers