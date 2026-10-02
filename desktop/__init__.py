"""STOCK_BOT Module 5 desktop application contracts."""

from .application import DesktopApplication, DesktopSnapshot
from .read_models import (
    DecisionTimelineEvent,
    DecisionTimelineState,
    ExplanationItem,
    ExplanationState,
    MarketDashboardState,
    ModelTelemetryState,
    PaperAccountState,
    PredictionPanelState,
    ReplayState,
    ResearchEvidenceItem,
    ResearchPanelState,
    RiskPanelState,
    ScreenObserverPanelState,
    build_explanation,
    build_market_dashboard,
    build_model_telemetry,
    build_paper_account,
    build_prediction_panel,
    build_research_panel,
    build_risk_panel,
    build_screen_panel,
    build_timeline,
    start_replay,
)
from .shell import DesktopShell, DesktopView

__all__ = [
    "DesktopShell", "DesktopView", "DesktopApplication", "DesktopSnapshot",
    "MarketDashboardState", "PredictionPanelState", "ExplanationItem",
    "ExplanationState", "ResearchEvidenceItem", "ResearchPanelState",
    "ScreenObserverPanelState", "DecisionTimelineEvent", "DecisionTimelineState",
    "ModelTelemetryState", "RiskPanelState", "PaperAccountState", "ReplayState",
    "build_market_dashboard", "build_prediction_panel", "build_explanation",
    "build_research_panel", "build_screen_panel", "build_timeline",
    "build_model_telemetry", "build_risk_panel", "build_paper_account", "start_replay",
]
