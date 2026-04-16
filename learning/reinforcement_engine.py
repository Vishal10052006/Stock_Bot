class ReinforcementEngine:

    def calculate_reward(self, predicted, actual):
        error = abs(predicted - actual)

        if error < 0.1:
            return 1.0
        elif error < 0.3:
            return 0.5
        else:
            return -0.5   # punish bad decisions

    def generate_feedback(self, factors, reward):
        feedback = {}

        for key, value in factors.items():
            feedback[key] = value * reward

        return feedback
    
    def update_weights(self, feedback):
        learning_rate = 0.05

        print("DEBUG feedback:", feedback)
        print("BEFORE:", self.weights)

        for key in self.weights:
            self.weights[key] = max(0.1, min(0.5, self.weights[key]))
            print("AFTER:", self.weights)

        self.normalize()

    def update(self, command, result):
        # 1. predicted (from result or fallback)
        predicted = result.get("confidence", 0.5)

        # 2. actual (convert success → score)
        success = result.get("success", True)
        actual = 1.0 if success else 0.0

        # 3. reward
        reward = self.calculate_reward(predicted, actual)

        # 4. factors (for now simple placeholder)
        factors = {
            "trust": 1,
            "risk": 1,
            "time": 1,
            "skill": 1,
            "goal": 1
        }

        # 5. feedback
        feedback = self.generate_feedback(factors, reward)

        # 6. update weights
        if hasattr(self, "weights"):
            self.update_weights(feedback)

        print(f"[Reinforcement] Reward: {reward}")