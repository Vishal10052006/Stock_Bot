class BaseWorker:

    name = "base_worker"
    capabilities = []

    def run(self, task):
        raise NotImplementedError