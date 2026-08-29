"""
Stock Bot — Reinforcement Engine

Phase 2 reinforcement-learning boundary.

Responsibilities:
    1. Compare predicted and observed outcomes.
    2. Calculate a reward from prediction error.
    3. Convert decision factors into reinforcement feedback.

The reinforcement engine does NOT:
    - select workers,
    - execute workers,
    - own adaptive weights,
    - update WeightManager directly.

Weight ownership and adaptive updates belong to WeightManager.
"""


class ReinforcementEngine:
    """Calculate rewards and generate learning feedback."""

    def calculate_reward(self, predicted, actual):
        """
        Calculate a reward from prediction accuracy.

        Args:
            predicted: Predicted execution confidence.
            actual: Observed execution outcome score.

        Returns:
            Reward value:
                1.0  -> highly accurate prediction
                0.5  -> moderately accurate prediction
               -0.5  -> poor prediction
        """

        error = abs(predicted - actual)

        if error < 0.1:
            return 1.0

        if error < 0.3:
            return 0.5

        return -0.5

    def generate_feedback(self, factors, reward):
        """
        Convert decision factors into reinforcement feedback.

        Args:
            factors: Decision-scoring factors.
            reward: Calculated reinforcement reward.

        Returns:
            Feedback dictionary for WeightManager.
        """

        return {
            key: value * reward
            for key, value in factors.items()
        }
