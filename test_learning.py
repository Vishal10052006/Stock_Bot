from core.ceo import CEO

ceo = CEO()

# simulate decision
result = ceo.simulate_decision("Build AI Study Assistant")

best = result["best_choice"]

# simulate real outcome (for now same)
actual = best["outcome"]

# record learning
ceo.learning_engine.record_outcome(
    result["goal"],
    best["option"],
    best["outcome"],
    actual
)

# check learning
stats = ceo.learning_engine.update_learning()

print(stats)