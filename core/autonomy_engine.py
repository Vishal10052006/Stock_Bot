from config.autonomy_rules import AUTONOMY_RULES

def check_permission(task_type):

    return AUTONOMY_RULES.get(task_type, "ASK")