"""Reproducible research experiment contracts."""

from .definition import ExperimentDefinition
from .evaluation import EvaluationReport, evaluate_experiment_record
from .executor import (
    ExperimentExecutionInputs,
    ExperimentLineageExecution,
    execute_validation_experiment,
    execute_validation_experiment_with_lineage,
)
from .failure_analysis import FailureAnalysisReport, FailureFinding, analyze_experiment_failure
from .lineage import LineageRecord, build_lineage
from .monitoring import MonitoringPolicy, MonitoringReport, MonitoringSnapshot, evaluate_monitoring
from .paper_quality import PaperEvidenceQualityReport, assess_paper_evidence
from .paper_journal import (
    PaperEvidenceJournal,
    PaperEvidenceRecord,
    persist_paper_decision_run,
)
from .paper_evidence import (
    PaperEvidenceCollector,
    PaperEvidenceReport,
    collect_paper_decision_run,
    PaperEvidenceSnapshot,
    validate_paper_evidence,
)
from .self_learning import LearningGateResult, LearningProposal, validate_learning_proposal
from .record import ExperimentRecord
from .runner import ExperimentExecution, ExperimentRunner

__all__ = [
    "EvaluationReport",
    "FailureAnalysisReport",
    "FailureFinding",
    "LearningGateResult",
    "LearningProposal",
    "LineageRecord",
    "MonitoringPolicy",
    "MonitoringReport",
    "MonitoringSnapshot",
    "PaperEvidenceCollector",
    "PaperEvidenceQualityReport",
    "PaperEvidenceReport",
    "collect_paper_decision_run",
    "PaperEvidenceSnapshot",
    "PaperEvidenceJournal",
    "PaperEvidenceRecord",
    "persist_paper_decision_run",
    "ExperimentDefinition",
    "ExperimentExecution",
    "ExperimentExecutionInputs",
    "ExperimentLineageExecution",
    "ExperimentRecord",
    "ExperimentRunner",
    "evaluate_experiment_record",
    "analyze_experiment_failure",
    "build_lineage",
    "evaluate_monitoring",
    "validate_paper_evidence",
    "assess_paper_evidence",
    "execute_validation_experiment",
    "execute_validation_experiment_with_lineage",
    "validate_learning_proposal",
]
