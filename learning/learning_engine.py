class LearningEngine:

    def __init__(self, memory_manager):
        """Initialize the learning engine with its memory dependency."""
        self.memory_manager = memory_manager

    # STORE DECISION RESULT
    def record_outcome(self, goal, chosen_option, predicted_outcome, actual_outcome):
        """Store a decision outcome in the configured memory manager."""
        entry = {
            "type": "decision_outcome",
            "goal": goal,
            "chosen_option": chosen_option,
            "predicted": predicted_outcome,
            "actual": actual_outcome
        }

        self.memory_manager.add_memory(entry)

    # COMPARE (LEARNING CORE)
    def evaluate_accuracy(self, predicted, actual):
        """Compare predicted and actual outcome fields."""
        score = 0
        total = len(predicted)

        for key in predicted:
            if key in actual and predicted[key] == actual[key]:
                score += 1

        accuracy = score / total if total > 0 else 0

        return accuracy

    # ADAPT FUTURE DECISIONS
    def update_learning(self):
        """Evaluate all stored decision outcomes."""
        memory = self.memory_manager.load_memory()

        outcomes = [
            m for m in memory
            if m.get("type") == "decision_outcome"
        ]

        if not outcomes:
            return {"message": "No learning data yet"}

        total_accuracy = 0

        for o in outcomes:
            acc = self.evaluate_accuracy(o["predicted"], o["actual"])
            total_accuracy += acc

        avg_accuracy = total_accuracy / len(outcomes)

        return {
            "total_cases": len(outcomes),
            "average_accuracy": avg_accuracy
        }

    def get_experience(self):
        """Return the number of stored memory entries."""
        memory = self.memory_manager.load_memory()
        return len(memory)

    def learn(self, command, result):
        """Store generic learning feedback through the memory manager."""
        success = result.get("success", True)
        confidence = result.get("confidence", 1.0)

        learning_data = {
            "command": command,
            "success": success,
            "confidence": confidence
        }

        self.memory_manager.store({
            "type": "learning",
            "data": learning_data
        })
