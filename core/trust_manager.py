class TrustManager:
    def __init__(self):
        self.trust_scores = {}

    def get_trust(self, worker_name):
        return self.trust_scores.get(worker_name, 0.5)

    def update_trust(self, worker_name, success, confidence=1.0):
        current = self.trust_scores.get(worker_name, 0.5)

        if success:
            current += 0.1 * confidence
        else:
            current -= 0.1 * confidence

        current = max(0.0, min(1.0, current))

        self.trust_scores[worker_name] = current

    def get_all_trust(self):
        return self.trust_scores