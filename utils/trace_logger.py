import json
from datetime import datetime
from core.execution_trace import ExecutionTrace

TRACE_FILE = "memory/execution_log.json"

def log_execution(trace: ExecutionTrace):

    try:
        with open(TRACE_FILE, "r") as f:
            data = json.load(f)

    except:
        data = []

    data.append(trace.__dict__)

    with open(TRACE_FILE, "w") as f:
        json.dump(data, f, indent=4) 
        