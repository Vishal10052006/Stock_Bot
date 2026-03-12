class Router:

    def __init__(self, registry):

        self.registry = registry

    def route(self, task):

        task_type = task["type"]

        workers = self.registry.get_workers(task_type)

        return workers