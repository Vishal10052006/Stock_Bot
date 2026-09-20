"""Research leakage audit for historical datasets."""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from research.datasets.schema import ResearchDatasetRow


@dataclass(frozen=True, slots=True)
class LeakageFinding:
    severity: str
    code: str
    message: str
    row_index: int


class ResearchLeakageAuditor:
    def audit(self, rows: tuple[ResearchDatasetRow, ...] | list[ResearchDatasetRow]) -> tuple[LeakageFinding, ...]:
        findings = []
        seen = set()
        for index, row in enumerate(rows):
            try:
                row.validate()
            except ValueError as exc:
                findings.append(LeakageFinding("ERROR", "ROW_VALIDATION", str(exc), index))
            key = (row.symbol, row.decision_time)
            if key in seen:
                findings.append(LeakageFinding("WARNING", "DUPLICATE_DECISION", "duplicate symbol/decision_time", index))
            seen.add(key)
        return tuple(findings)

    @staticmethod
    def summary(findings: tuple[LeakageFinding, ...]) -> dict[str, int]:
        return dict(Counter(f"{f.severity}:{f.code}" for f in findings))
