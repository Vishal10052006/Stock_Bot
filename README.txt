## Personal AI — Final System Architecture

User
  │
  ▼
main.py
  │
  ▼
CEO (Orchestrator)
  │
  ├── Planner
  │       │
  │       ▼
  │   Task Plan
  │
  ├── Router
  │       │
  │       ▼
  │   Detect Intent
  │
  ├── Worker Registry
  │       │
  │       ▼
  │   Available Workers
  │
  ├── Worker Loader
  │       │
  │       ▼
  │   Auto-load plugins
  │
  ├── Executor
  │       │
  │       ▼
  │   Run workers
  │
  ├── Critic
  │       │
  │       ▼
  │   Validate output
  │
  ├── Memory
  │       │
  │       ▼
  │   Store interactions
  │
  └── Formatter
          │
          ▼
       Final Output

