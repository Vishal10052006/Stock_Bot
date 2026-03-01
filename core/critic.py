class CriticAgent:

    def review(self, task_type: str, output: list):
        """
        Returns:
        {
            "decision": "approve" | "retry" | "reject",
            "reason": "explanation"
        }
        """

        # Simple rule-based critic (v1)
        combined_output = " ".join(output).lower()

        # Basic validation checks
        if len(combined_output) < 20:
            return{
                "decision": "reject",
                "reason": "Detected error in output."
            }
        
        if "error" in combined_output:
            return {
                "decision": "reject",
                "reason": "Detected error in output."
            }
        
        return{
            "decision": "approve",
            "reason": "Output looks valid."
        }
