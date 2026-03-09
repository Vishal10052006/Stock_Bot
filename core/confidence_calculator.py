from config.worker_reliability import WORKER_RELIABILITY

def calculate_confidence(worker_name: str, critic_score: float) -> float:

    reliability = WORKER_RELIABILITY.get(worker_name, 0.5)

    confidence = (reliability + critic_score) / 2

    return round(confidence, 2)