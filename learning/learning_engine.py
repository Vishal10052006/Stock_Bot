"""
Stock Bot - Learning Engine

Records decision outcomes, evaluates prediction accuracy,
and provides historical learning information.
"""

class LearningEngine:

    def __init__(self, memory_manager):
        """Initialize the learning engine with the shared memory manager."""

        # Store the injected memory dependency consistently.
        self.memory_manager = memory_manager

    # ------------------------------------------------------------------
    # STORE DECISION RESULT
    # ------------------------------------------------------------------
    def record_outcome(
        self,
        goal,
        chosen_option,
        predicted_outcome,
        actual_outcome
    ):
        """Store the result of a completed decision."""

        entry = {
            "type": "decision_outcome",
            "goal": goal,
            "chosen_option": chosen_option,
            "predicted": predicted_outcome,
            "actual": actual_outcome
        }

        # Use the injected MemoryManager consistently.
        self.memory_manager.add_memory(entry)

    # ------------------------------------------------------------------
    # COMPARE PREDICTION WITH ACTUAL RESULT
    # ------------------------------------------------------------------
    def evaluate_accuracy(self, predicted, actual):
        """Return the percentage of matching predicted fields."""

        score = 0
        total = len(predicted)

        for key in predicted:
            if key in actual and predicted[key] == actual[key]:
                score += 1

        accuracy = score / total if total > 0 else 0

        return accuracy

    # ------------------------------------------------------------------
    # ADAPT FUTURE DECISIONS
    # ------------------------------------------------------------------
    def update_learning(self):
        """Calculate average accuracy from stored decision outcomes."""

        # Use the injected MemoryManager consistently.
        memory = self.memory_manager.load_memory()

        outcomes = [
            entry
            for entry in memory
            if entry.get("type") == "decision_outcome"
        ]

        if not outcomes:
            return {
                "message": "No learning data yet"
            }

        total_accuracy = 0

        for outcome in outcomes:
            accuracy = self.evaluate_accuracy(
                outcome["predicted"],
                outcome["actual"]
            )
            total_accuracy += accuracy

        average_accuracy = total_accuracy / len(outcomes)

        return {
            "total_cases": len(outcomes),
            "average_accuracy": average_accuracy
        }

    # ------------------------------------------------------------------
    # EXPERIENCE
    # ------------------------------------------------------------------
    def get_experience(self):
        """Return the number of stored memory entries."""

        return len(self.memory_manager.load_memory())

    # ------------------------------------------------------------------
    # GENERAL LEARNING
    # ------------------------------------------------------------------
    def learn(self, command, result):
        """Store the outcome of a general execution."""

        success = result.get("success", True)
        confidence = result.get("confidence", 1.0)

        learning_data = {
            "command": command,
            "success": success,
            "confidence": confidence
        }

        # Store learning data through the shared memory manager.
        self.memory_manager.store({
            "type": "learning",
            "data": learning_data
        })