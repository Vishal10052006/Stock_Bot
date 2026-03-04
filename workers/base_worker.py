class BaseWorker:

    def __init__(self, name: str, capabilities: list, risk_level: str = "low"):
        self.name = name
        self.capabilities = capabilities
        self.risk_level = risk_level

    async def execute(self, task: str):
        raise NotImplementedError("Worker must implement execute()")