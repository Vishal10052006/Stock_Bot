# decision_simulator

class DecisionSimulator:

    def generate_options(self, goal):
        goal = goal.lower()

        if "blog" in goal:
            return [
                {"option": "Publish daily"},
                {"option": "Publish weekly"}
            ]

        elif "ai" in goal:
            return [
                {"option": "Build backend first"},
                {"option": "Build UI first"},
                {"option": "Build both in parallel"}
            ]

        else:
            return [
                {"option": f"Fast execution of {goal}"},
                {"option": f"Careful planning of {goal}"}
            ]
        
    # OUTCOME PREDICTION    
    def simulate_outcomes(self, option):
        text = option["option"].lower()

        result = {}

        if "daily" in text:
            result = {
                "quality": "low",
                "burnout": "high",
                "growth": "fast"
            }

        elif "weekly" in text:
            result = {
                "quality": "high",
                "burnout": "low",
                "growth": "slow"
            }

        elif "backend" in text:
            result = {
                "stability": "high",
                "speed": "medium",
                "risk": "low"
            }

        elif "ui" in text:
            result = {
                "user_experience": "high",
                "stability": "low",
                "risk": "medium"
            }

        else:
            result = {
                "quality": "medium",
                "risk": "medium"
            }

        option["outcome"] = result
        return option
    
    # SCORING ENGINE
    def score_option(self, option):
        outcome = option["outcome"]

        score = 0

        for key, value in outcome.items():

            # Positive Signals
            if value in ["high", "fast"]:
                score += 2

            # Neutral
            elif value == "medium":
                score += 1

            # Negative
            elif value in ["low"]:
                score += 0

            # 🔥 RISK PENALTY
            if key == "risk":
                if value == "high":
                    score -= 1
                elif value == "medium":
                    score -= 1

        option["score"] = score
        return option
    
    # FULL DECISION PIPELINE
    def simulate(self, goal):
        options = self.generate_options(goal)

        results = []

        for opt in options:
            opt = self.simulate_outcomes(opt)
            opt = self.score_option(opt)
            opt = self.analyze_tradeoffs(opt)

            results.append(opt)

        best = max(results, key=lambda x: x["score"])

        explanation = self.explain_decision(best)

        return {
            "goal": goal,
            "options": results,
            "best_choice": best,
            "explanation": explanation
        }
    
    # TRADE-OFF ANALYSIS
    def analyze_tradeoffs(self, option):
        outcome = option["outcome"]

        pros = []
        cons = []

        for key, value in outcome.items():

            # GOOD things
            if value in ["high", "fast"]: 
                pros.append(f"{key} is {value}")

            # BAD things
            elif value in ["low"]:
                if key == "risk":
                    pros.append(f"{key} is low")  # 🔥 risk low = GOOD
                else:
                    cons.append(f"{key} is low")

            # MEDIUM = neutral (optional)
            elif value == "medium":
                cons.append(f"{key} is medium")

        option["pros"] = pros
        option["cons"] = cons

        return option
        
    # EXPLANATION ENGINE (MOST IMPORTANT)
    def explain_decision(self, best_option):
        pros = best_option.get("pros", [])
        cons = best_option.get("cons", [])

        explanation = f"Best choice is '{best_option['option']}' because:\n"

        if pros:
            explanation += "Pros:\n"
            for p in pros:
                explanation += f"- {p}\n"

        if cons:
            explanation += "Cons:\n"
            for c in cons:
                explanation += f"- {c}\n"

        return explanation