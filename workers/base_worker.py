class BaseWorker:
    def __init__(self, name: str):
        self.name = name

    def execute(self, task: str):
        raise NotImplementedError("Execute method must be implemented by subclass.")
