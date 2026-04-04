class WeightManager:
    def __init__(self):
        self.weights = {
            "trust": 0.2,
            "risk": 0.2,
            "time": 0.2,
            "skill": 0.2,
            "goal": 0.2
        }

    def get_weights(self):
        return self.weights

    def update_weights(self, feedback):
        learning_rate = 0.05

        for key in self.weights:
            self.weights[key] += learning_rate * feedback.get(key, 0)

        self.normalize()

    def normalize(self):
        total = sum(self.weights.values())
        for k in self.weights:
            self.weights[k] /= total