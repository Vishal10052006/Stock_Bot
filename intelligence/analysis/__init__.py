"""Analysis Bot package."""

from intelligence.analysis.contracts import (
    ANALYSIS_VERSION,
    FEATURE_CONTEXT_VERSION,
    AnalysisContext,
    AnalysisInput,
    AnalysisContractError,
)
from intelligence.analysis.engine import AnalysisEngine, analyze_latest_row
from intelligence.analysis.fundamentals import (
    FUNDAMENTAL_VERSION,
    FundamentalContractError,
    FundamentalSnapshot,
    ValuationSnapshot,
    FundamentalProvider,
    InMemoryFundamentalProvider,
    FundamentalAlignmentError,
    align_fundamental_snapshot,
    analyze_fundamentals,
)

__all__ = [
    "ANALYSIS_VERSION",
    "FEATURE_CONTEXT_VERSION",
    "AnalysisContext",
    "AnalysisInput",
    "AnalysisContractError",
    "AnalysisEngine",
    "analyze_latest_row",
    "FUNDAMENTAL_VERSION",
    "FundamentalContractError",
    "FundamentalSnapshot",
    "ValuationSnapshot",
    "FundamentalProvider",
    "InMemoryFundamentalProvider",
    "FundamentalAlignmentError",
    "align_fundamental_snapshot",
    "analyze_fundamentals",
]
