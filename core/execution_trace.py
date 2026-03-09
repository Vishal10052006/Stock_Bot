from dataclasses import dataclass
from datetime import datetime

@dataclass
class ExecutionTrace:

    task_type: str
    worker: str
    confidence: float
    risk: float
    decision: str
    result: str
    timestamp: str
    