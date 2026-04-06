class CriticAgent:

    def review(self, plan: list, task_type: str, outputs: list):

        # PLAN VALIDATION
        if not plan:
            return {"decision": "reject", "reason": "Execution plan is empty."}

        if len(plan) > 5:
            return {
                "decision": "retry",
                "reason": "Plan too complex. Simplify task."
            }

            # Example rule: publish should not come before writing
            if "publish" in intents_sequence and "writing" not in intents_sequence:
                return {
                    "decision": "reject",
                    "reason": "Invalid plan: publishing without writing."
                }

        # OUTPUT VALIDATION
        combined_output = " ".join(outputs).strip()
        combined_lower = combined_output.lower()

        if not combined_output:
            return {"decision": "reject", "reason": "Output is empty."}

        if len(combined_output) < 25:
            return {"decision": "retry", "reason": "Output too short. Expand more."}

        if "traceback" in combined_lower or "exception" in combined_lower:
            return {"decision": "reject", "reason": "System error detected."}

        return {"decision": "approve", "reason": "Plan and output validated."}