def format_success(task_type, result):
    return(
        f"\n=== TASK RESULT ===\n"
        f"Task Type : {task_type}\n"
        f"Status    : Success\n"
        f"Output    : \n{result}\n"
        f"=====================\n"
    )

def format_error(message):
    return(
        f"\n=== ERROR ===\n"
        f"Status : Failed\n"
        f"Reason : {message}\n"
        f"=================\n"
    )