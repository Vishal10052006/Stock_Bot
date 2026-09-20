"""RB-11 deterministic research report generator with provenance."""
from __future__ import annotations
from research.contracts import ResearchContext


class ResearchReportGenerator:
    def generate(self, context: ResearchContext) -> str:
        lines = [
            f"Research report: {context.symbol}",
            f"As-of: {context.as_of.isoformat()}",
            f"Research version: {context.research_version}",
            f"Sources: {context.source_count}",
            "",
            f"Documents: {len(context.documents)}",
            f"Events: {len(context.events)}",
        ]
        for event in context.events:
            lines.append(f"- {event.event_type.value}: {event.evidence} (confidence={event.confidence:.2f})")
        lines.append("")
        lines.append("Provenance:")
        lines.extend(f"- {item}" for item in context.provenance)
        return "\n".join(lines)
