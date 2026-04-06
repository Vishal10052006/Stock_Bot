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