class CriticAgent:

    def review(self, task_type: str, outputs: list):

        combined_output = " ".join(outputs).strip()
        combined_lower = combined_output.lower()

        # Basic Empty Check
        if not combined_output:
            return {
                "decision": "reject",
                "reason": "Output is empty."
            }

        # Short Output Check
        if len(combined_output) < 25:
            return {
                "decision": "retry",
                "reason": "Output too short. Expand more."
            }

        # Writing Task Checks
        if task_type.lower().startswith("writing"):
            if "blog" in combined_lower and len(combined_output.split()) < 10:
                return {
                    "decision": "retry",
                    "reason": "Blog content too small."
                }

        # Research Task Checks
        if task_type.lower().startswith("research"):
            if "research" not in combined_lower:
                return {
                    "decision": "retry",
                    "reason": "Research output lacks explanation."
                }

        # Detect obvious error text
        if "traceback" in combined_lower or "exception" in combined_lower:
            return {
                "decision": "reject",
                "reason": "System error detected."
            }

        return {
            "decision": "approve",
            "reason": "Output passed review."
        }