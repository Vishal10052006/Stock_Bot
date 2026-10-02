"""Module 5 desktop composition for D01-D10.

This is a framework-neutral application contract. A future GUI adapter can bind
these views to Qt/Tk/web/native widgets without moving trading authority into
the desktop layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .read_models import (
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


@dataclass(frozen=True, slots=True)
class DesktopSnapshot:
    navigation: Mapping[str, Any]
    views: Mapping[str, Any]
    authority: str = "OBSERVATION_ONLY"

    def as_dict(self) -> dict[str, Any]:
        return {
            "navigation": dict(self.navigation),
            "views": dict(self.views),
            "authority": self.authority,
        }


class DesktopApplication:
    """Read-only composition root for the D01-D10 desktop interface."""

    VIEW_ORDER = (
        ("market", "Market Dashboard"),
        ("prediction", "Prediction"),
        ("explanation", "Explanation"),
        ("research", "Research / News"),
        ("screen", "Screen Observer"),
        ("timeline", "Decision Timeline"),
        ("telemetry", "Model Telemetry"),
        ("risk", "Risk"),
        ("paper", "Paper Account"),
        ("replay", "Session Replay"),
    )

    def __init__(self) -> None:
        self.shell = DesktopShell(
            DesktopView(view_id, title, order=index)
            for index, (view_id, title) in enumerate(self.VIEW_ORDER)
        )

    def snapshot(
        self,
        *,
        market: Any = None,
        monitoring: Any = None,
        prediction: Any = None,
        decision_chain: Any = None,
        research: Any = (),
        screen_observation: Any = None,
        screen_reconciliation: Any = None,
        screen_validation: Any = None,
        timeline_events: Any = (),
        risk: Any = None,
        safety: Any = None,
        paper_runtime: Any = None,
        paper_prices: Mapping[str, float] | None = None,
        replay_session_id: str | None = None,
        replay_events: Any = (),
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> DesktopSnapshot:
        timeline = build_timeline(timeline_events)
        replay = start_replay(replay_session_id, replay_events)
        return DesktopSnapshot(
            navigation=self.shell.snapshot(),
            views={
                "market": build_market_dashboard(
                    market=market, monitoring=monitoring, symbol=symbol, timeframe=timeframe
                ).as_dict(),
                "prediction": build_prediction_panel(prediction).as_dict(),
                "explanation": build_explanation(decision_chain).as_dict(),
                "research": build_research_panel(
                    research,
                    decision_timestamp=getattr(decision_chain, "analysis", None)
                    and getattr(getattr(decision_chain, "analysis", None), "timestamp", None),
                ).as_dict(),
                "screen": build_screen_panel(
                    screen_observation,
                    reconciliation=screen_reconciliation,
                    validation=screen_validation,
                ).as_dict(),
                "timeline": timeline.as_dict(),
                "telemetry": build_model_telemetry(monitoring).as_dict(),
                "risk": build_risk_panel(risk, safety=safety).as_dict(),
                "paper": build_paper_account(
                    paper_runtime, prices=paper_prices
                ).as_dict(),
                "replay": replay.as_dict(),
            },
        )


__all__ = ["DesktopApplication", "DesktopSnapshot"]
