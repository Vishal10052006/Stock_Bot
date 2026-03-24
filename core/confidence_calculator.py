from core.reliability_manager import calculate_worker_reliability

def calculate_confidence(worker_name, critic_score):

    reliability = calculate_worker_reliability(worker_name)

    confidence = (reliability + critic_score) / 2

    return round(confidence, 2)