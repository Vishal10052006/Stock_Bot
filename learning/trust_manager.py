class TrustManager:
    def __init__(self):
        self.trust_scores = {}

    def get_trust(self, worker_name):
        return self.trust_scores.get(worker_name, 0.5)

    def update_trust(self, worker_name, success, confidence=1.0):

        # 1. Apply decay to ALL workers FIRST
        for w in self.trust_scores:
            self.trust_scores[w] *= 0.98   # small decay

        # 2. Get current trust
        current = self.trust_scores.get(worker_name, 0.5)

        # 3. Update based on result
        if success:
            current += 0.1 * confidence
        else:
            current -= 0.1 * confidence

        # 4. Clamp between 0 and 1
        current = max(0.0, min(1.0, current))

        # 5. Save back
        self.trust_scores[worker_name] = current

    def get_all_trust(self):
        return self.trust_scores
    
    def update(self, worker_name, result):
        success = result.get("success", True)

        if worker_name not in self.trust_scores:
            self.trust_scores[worker_name] = 0.5  # default trust

        if success:
            self.trust_scores[worker_name] += 0.05
        else:
            self.trust_scores[worker_name] -= 0.05

        # clamp between 0 and 1
        self.trust_scores[worker_name] = max(0.0, min(1.0, self.trust_scores[worker_name]))

        print(f"[Trust] {worker_name}: {self.trust_scores[worker_name]:.2f}")