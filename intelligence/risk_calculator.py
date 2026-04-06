from config.risk_rules import TASK_RISK

def calculate_risk(task_type: str) -> float:

    risk = TASK_RISK.get(task_type, 0.5)

    return round(risk, 2)