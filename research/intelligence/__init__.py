"""Research Intelligence public API.

Exports the model eagerly and the orchestration pipeline lazily so importing
research.integration does not create a circular dependency.
"""

from research.intelligence.model import (
    ResearchIntelligenceModel,
    ResearchIntelligenceResult,
)


def __getattr__(name: str):
    if name in {"ResearchIntelligencePipeline", "ResearchIntelligenceRun"}:
        from research.intelligence.pipeline import (
            ResearchIntelligencePipeline,
            ResearchIntelligenceRun,
        )
        return {
            "ResearchIntelligencePipeline": ResearchIntelligencePipeline,
            "ResearchIntelligenceRun": ResearchIntelligenceRun,
        }[name]
    raise AttributeError(name)


__all__ = [
    "ResearchIntelligenceModel",
    "ResearchIntelligenceResult",
    "ResearchIntelligencePipeline",
    "ResearchIntelligenceRun",
]
