from core.ceo import CEO

ceo = CEO()

ceo.add_goal("Build AI Study Assistant")

strategies = ceo.plan_strategies()

for s in strategies:
    print(s)