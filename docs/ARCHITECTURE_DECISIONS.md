# Stock Bot — Architecture Decisions

## Purpose

Transform the existing Personal AI codebase into a personal intraday
stock-analysis and paper-trading system.

The system must prioritize:
- Market-data correctness
- Reproducible analysis
- Risk management
- Backtesting
- Paper trading
- Measurable model performance
- Learning from validated outcomes

Real-money trading must remain disabled until validation requirements
are satisfied.

---

## Existing Components

### Keep / Adapt

- Worker interface
- Worker registry concept
- Strategy selection concept
- Reliability tracking concept
- Emergency shutdown concept

### Replace

- TechnicalWorker
- SentimentWorker
- LearningEngine core
- ReinforcementEngine
- MemoryManager
- SafetyManager
- Generic risk rules
- Generic autonomy rules

### Remove from Core Trading Logic

- Generic goal-management behavior
- Generic session-memory behavior
- Generic task-risk categories
- Generic autonomous-agent behavior

---

## Target Architecture

```text
Market Data
    |
    v
Feature / Indicator Engine
    |
    v
Signal Generation
    |
    +---- Technical Analysis
    +---- Sentiment
    +---- Market Regime
    +---- ML Prediction
    |
    v
Strategy Engine
    |
    v
Risk Engine
    |
    v
Decision Engine
    |
    v
Execution Gate
    |
    v
Paper Trading
    |
    v
Trade Results
    |
    v
Evaluation / Learning
