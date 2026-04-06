# safety/safety_manager.py

MAX_RISK = 0.8

def is_safe(action: dict) -> bool:
    """
    Check if action is safe to execute
    """
    risk = action.get("risk", 0)
    return risk <= MAX_RISK