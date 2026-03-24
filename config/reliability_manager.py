import json

LOG_FILE = "memory/execution_log.json"

def calculate_worker_reliability(worker_name):

    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
    except:
        return 0.5

    runs = [log for log in logs if log["worker"] == worker_name]

    if not runs:
        return 0.5

    success = [log for log in runs if log["result"] == "SUCCESS"]

    return round(len(success) / len(runs), 2)