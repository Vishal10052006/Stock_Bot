"""
Stock Bot — Critic Agent

Validates execution plans and evaluates worker outputs.

The critic is intentionally deterministic in Phase 1 so that the
execution pipeline can be tested reliably before introducing more
advanced evaluation models.
"""


class CriticAgent:
    """Validate plans and score worker outputs."""

    def score(self, output):
        """
        Convert a worker output into a quality score in the range [0, 1].

        Worker outputs normally follow the standard dictionary contract:
            {
                "success": bool,
                ...
            }

        Args:
            output: Worker execution result.

        Returns:
            Float score between 0.0 and 1.0.
        """

        if output is None:
            return 0.0

        if isinstance(output, Exception):
            return 0.0

        if isinstance(output, dict):
            if output.get("success") is False:
                return 0.0

            if output.get("success") is True:
                # Worker confidence provides a useful Phase-1 quality
                # signal while keeping the critic deterministic.
                confidence = output.get("confidence", 1.0)

                try:
                    confidence = float(confidence)
                except (TypeError, ValueError):
                    return 0.0

                return max(0.0, min(1.0, confidence))

        # Preserve support for simple textual worker outputs.
        if isinstance(output, str):
            if not output.strip():
                return 0.0

            return 1.0 if len(output.strip()) >= 25 else 0.5

        return 0.5

    def review(self, plan: list, task_type: str, outputs: list):
        """
        Perform final plan and output validation.

        Args:
            plan: Execution plan.
            task_type: Current task intent.
            outputs: Worker outputs.

        Returns:
            Review dictionary containing decision and reason.
        """

        # PLAN VALIDATION
        if not plan:
            return {
                "decision": "reject",
                "reason": "Execution plan is empty.",
            }

        if len(plan) > 5:
            return {
                "decision": "retry",
                "reason": "Plan too complex. Simplify task.",
            }

        # Validate plan ordering.
        intents_sequence = [
            step.get("intent", "").lower()
            for step in plan
        ]

        # Publishing requires a preceding writing step.
        if "publish" in intents_sequence and "writing" not in intents_sequence:
            return {
                "decision": "reject",
                "reason": "Invalid plan: publishing without writing.",
            }

        # OUTPUT VALIDATION
        if not outputs:
            return {
                "decision": "reject",
                "reason": "Output is empty.",
            }

        valid_outputs = [
            output
            for output in outputs
            if not isinstance(output, Exception)
        ]

        if not valid_outputs:
            return {
                "decision": "reject",
                "reason": "All worker executions failed.",
            }

        # Score the final outputs.
        scores = [
            self.score(output)
            for output in valid_outputs
        ]

        if max(scores) <= 0.0:
            return {
                "decision": "reject",
                "reason": "Worker output failed validation.",
            }

        return {
            "decision": "approve",
            "reason": "Plan and output validated.",
        }
