class BaseWorker:

    def __init__(self, name, capabilities, risk_level="low"):
        self.name = name
        self.capabilities = capabilities
        self.risk_level = risk_level

    async def execute(self, task: str):
        raise NotImplementedError