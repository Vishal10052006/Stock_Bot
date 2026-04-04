class ReinforcementEngine:

    def calculate_reward(self, predicted, actual):
        return (actual - predicted) * 2

    def generate_feedback(self, factors, reward):
        feedback = {}

        for key, value in factors.items():
            if reward < 0:
                feedback[key] = reward * value * 2   # stronger punishment
            else:
                feedback[key] = reward * value

        return feedback