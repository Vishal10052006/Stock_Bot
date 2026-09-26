from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .contracts import AgentStatus, DashboardConfig
from .registry import PIPELINE, SOURCE_TO_AGENT, agent_records


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DashboardService:
    config: DashboardConfig
    monitoring: Any = None
    journal: Any = None
    model_registry: Any = None

    @classmethod
    def from_environment(cls, config: DashboardConfig | None = None):
        config = config or DashboardConfig(
            journal_path=os.getenv(
                "STOCK_BOT_MONITORING_JOURNAL",
                "data/monitoring/dashboard.jsonl",
            ),
            environment=os.getenv("STOCK_BOT_ENVIRONMENT", "RESEARCH/PAPER"),
        )
        journal = None
        try:
            from monitoring.journal import MonitoringJournal

            journal = MonitoringJournal(config.journal_path)
        except Exception:
            pass
        return cls(config, journal=journal)

    def _events(self) -> list[dict[str, Any]]:
        if self.journal is None:
            return []
        try:
            return [event.to_dict() for event in self.journal.events()]
        except (OSError, ValueError, TypeError):
            return []

    def _monitoring_payload(self) -> dict[str, Any]:
        if self.monitoring is None:
            return {}
        try:
            payload = (
                self.monitoring.dashboard()
                if hasattr(self.monitoring, "dashboard")
                else {}
            )
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def agents(self) -> list[dict[str, Any]]:
        health = {
            str(item.get("component", "")).lower(): item
            for item in self._monitoring_payload().get("health", [])
            if isinstance(item, dict)
        }
        events = self._events()
        output = []
        mapping = {
            "HEALTHY": AgentStatus.ACTIVE.value,
            "DEGRADED": AgentStatus.DEGRADED.value,
            "UNHEALTHY": AgentStatus.FAILED.value,
            "UNKNOWN": AgentStatus.UNKNOWN.value,
        }

        for agent in agent_records():
            keys = (
                agent["agent_id"].lower(),
                agent["name"].lower(),
                agent["name"].lower().replace("_bot", ""),
            )
            observed_health = next(
                (health[key] for key in keys if key in health),
                None,
            )

            status = (
                AgentStatus.LOCKED.value
                if agent["locked"]
                else AgentStatus.WAITING.value
            )

            if observed_health:
                status = mapping.get(
                    str(observed_health.get("status", "UNKNOWN")).upper(),
                    AgentStatus.UNKNOWN.value,
                )

            related = [
                event
                for event in events
                if SOURCE_TO_AGENT.get(str(event.get("source", "")).lower())
                == agent["agent_id"]
            ]

            if not observed_health and related:
                health_events = [
                    event
                    for event in related
                    if str(event.get("event_type", "")).upper() == "HEALTH"
                ]
                if health_events:
                    severity = str(
                        health_events[-1].get("severity", "INFO")
                    ).upper()
                    status = mapping.get(severity, AgentStatus.UNKNOWN.value)

            output.append(
                {
                    **agent,
                    "status": status,
                    "observed": bool(observed_health),
                    "event_count": len(related),
                    "last_event": related[-1] if related else None,
                }
            )
        return output

    def pipeline(self) -> list[dict[str, Any]]:
        agents = {agent["agent_id"]: agent for agent in self.agents()}
        events = self._events()
        output = []

        for stage_id, name, agent_id in PIPELINE:
            related = [
                event
                for event in events
                if SOURCE_TO_AGENT.get(str(event.get("source", "")).lower())
                == agent_id
            ]
            agent = agents[agent_id]
            detail = (
                str(related[-1].get("event_type"))
                if related
                else (
                    "LIVE BROKER LOCKED; PAPER ONLY"
                    if agent["status"] == "LOCKED"
                    else "WAITING FOR TELEMETRY"
                )
            )
            output.append(
                {
                    "stage_id": stage_id,
                    "name": name,
                    "agent_id": agent_id,
                    "status": agent["status"],
                    "detail": detail,
                    "event_count": len(related),
                }
            )
        return output

    def models(self) -> list[dict[str, Any]]:
        if self.model_registry is None:
            return []
        try:
            return [
                self.model_registry.get(version).to_dict()
                for version in self.model_registry.versions()
            ]
        except Exception:
            return []

    def events(
        self,
        limit: int = 100,
        source: str | None = None,
        event_type: str | None = None,
        correlation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items = self._events()
        if source:
            items = [event for event in items if event.get("source") == source]
        if event_type:
            items = [
                event for event in items if event.get("event_type") == event_type
            ]
        if correlation_id:
            items = [
                event
                for event in items
                if event.get("correlation_id") == correlation_id
            ]
        return items[-max(1, min(int(limit), 1000)) :]

    def decisions(self, correlation_id: str | None = None) -> list[dict[str, Any]]:
        events = self.events(1000, correlation_id=correlation_id)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            grouped.setdefault(
                event.get("correlation_id") or event["event_id"], []
            ).append(event)

        return [
            {
                "decision_id": decision_id,
                "timestamp": events[-1]["timestamp"],
                "event_count": len(events),
                "stages": [
                    {
                        "source": event["source"],
                        "event_type": event["event_type"],
                        "severity": event["severity"],
                        "timestamp": event["timestamp"],
                    }
                    for event in events
                ],
                "events": events,
            }
            for decision_id, events in list(grouped.items())[-100:]
        ]

    def learning(self) -> dict[str, Any]:
        events = self._events()
        keys = (
            "OUTCOME",
            "ERROR",
            "EXPERIENCE",
            "DATASET",
            "RETRAIN",
            "OOS",
            "PROMOTION",
        )
        counts = {key: 0 for key in keys}

        for event in events:
            blob = (
                str(event.get("event_type", ""))
                + " "
                + str(event.get("source", ""))
            ).upper()
            for key in keys:
                if key in blob:
                    counts[key] += 1

        return {
            "stages": [
                {"stage": index + 1, "name": name, "count": counts[key]}
                for index, (name, key) in enumerate(
                    (
                        ("TRADE OUTCOME", "OUTCOME"),
                        ("ERROR ANALYSIS", "ERROR"),
                        ("EXPERIENCE ACCRUAL", "EXPERIENCE"),
                        ("DATASET UPDATE", "DATASET"),
                        ("MODEL RETRAINING", "RETRAIN"),
                        ("OOS / WALK-FORWARD", "OOS"),
                        ("PROMOTION GATE", "PROMOTION"),
                    )
                )
            ],
            "authoritative": False,
        }

    def health(self) -> dict[str, Any]:
        return {
            "monitoring": self._monitoring_payload(),
            "live_trading": "LOCKED",
            "live_order_submission": False,
            "paper_mode": True,
            "causality": "ENFORCED",
            "event_count": len(self._events()),
        }

    def overview(self) -> dict[str, Any]:
        agents = self.agents()
        events = self.events(50)
        summary = {
            "registered_agents": len(agents),
            "active": sum(agent["status"] == "ACTIVE" for agent in agents),
            "waiting": sum(agent["status"] == "WAITING" for agent in agents),
            "standby": sum(agent["status"] == "STANDBY" for agent in agents),
            "locked": sum(agent["status"] == "LOCKED" for agent in agents),
            "degraded": sum(agent["status"] == "DEGRADED" for agent in agents),
            "failed": sum(agent["status"] == "FAILED" for agent in agents),
            "events": len(self._events()),
        }
        return {
            "timestamp": _now(),
            "environment": self.config.environment,
            "causality": "ENFORCED",
            "live_trading": "LOCKED",
            "paper_only": True,
            "agents": agents,
            "pipeline": self.pipeline(),
            "models": self.models(),
            "learning": self.learning(),
            "health": self.health(),
            "events": events,
            "summary": summary,
        }

    def replay(self, correlation_id: str | None):
        return self.events(1000, correlation_id=correlation_id)

    def chat(self, message: str, history: list[Any] | None = None) -> dict[str, Any]:
        """Ask the OPS assistant using current dashboard state plus optional live web search."""
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        snapshot = self.overview()

        if not api_key:
            return {
                "answer": (
                    "OPS AI is installed, but OPENAI_API_KEY is not configured. "
                    "I can still report the local dashboard state, but I cannot "
                    "perform live market research until an API key is supplied.\n\n"
                    f"Current system: {snapshot['summary']['registered_agents']} agents, "
                    f"{snapshot['summary']['events']} telemetry events, "
                    f"live trading {snapshot['live_trading'].lower()}."
                ),
                "configured": False,
                "sources": [],
            }

        model = os.getenv("STOCK_BOT_AI_MODEL", "gpt-5.5")
        recent_history = []
        for item in (history or []):
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                recent_history.append({"role": role, "content": content[:4000]})

        system_instruction = (
            "You are JARVIS, the conversational intelligence layer of STOCK_BOT OPS CENTER. "
            "Be concise, precise, calm and operational. You may explain the trading system, "
            "current dashboard state, market context, research and model observations. "
            "When the user asks about the current overall market or current market events, "
            "use live web search and clearly distinguish sourced facts from interpretation. "
            "Never invent telemetry, prices, positions, fills, signals, model results or agent health. "
            "If dashboard telemetry is missing, say it is missing. "
            "You are NOT the Strategy, Risk or Execution authority. Never place orders, change risk, "
            "authorize trades, or claim that a trade should be executed. Live trading is locked. "
            "Treat future outcome labels as labels only and preserve point-in-time causality. "
            "When useful, summarize: market regime, major drivers, volatility, breadth, sector context, "
            "relevant events, and what the STOCK_BOT pipeline currently observes. "
            "For a direct system-status question, prefer the supplied dashboard snapshot over general knowledge."
        )

        context = {
            "dashboard_timestamp": snapshot["timestamp"],
            "environment": snapshot["environment"],
            "summary": snapshot["summary"],
            "pipeline": snapshot["pipeline"],
            "agents": [
                {
                    "agent_id": agent["agent_id"],
                    "name": agent["name"],
                    "status": agent["status"],
                    "observed": agent["observed"],
                    "event_count": agent["event_count"],
                }
                for agent in snapshot["agents"]
            ],
            "learning": snapshot["learning"],
            "health": snapshot["health"],
            "recent_events": snapshot["events"][-20:],
        }

        input_items = [
            {
                "role": "developer",
                "content": system_instruction
                + "\n\nCURRENT DASHBOARD SNAPSHOT (authoritative for local runtime state):\n"
                + json.dumps(context, separators=(",", ":"), default=str),
            }
        ]
        input_items.extend(recent_history)
        input_items.append({"role": "user", "content": message[:8000]})

        body = json.dumps(
            {
                "model": model,
                "input": input_items,
                "tools": [{"type": "web_search", "search_context_size": "low"}],
                "tool_choice": "auto",
                "store": False,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "STOCK_BOT-OPS-CENTER/1.1",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API connection failed: {exc.reason}") from exc

        answer = str(result.get("output_text", "")).strip()
        if not answer:
            for item in result.get("output", []):
                if item.get("type") != "message":
                    continue
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        answer += str(content.get("text", ""))
            answer = answer.strip()

        sources = []
        for item in result.get("output", []):
            for content in item.get("content", []):
                for annotation in content.get("annotations", []) or []:
                    if annotation.get("type") == "url_citation":
                        url = annotation.get("url")
                        title = annotation.get("title") or url
                        if url and not any(source["url"] == url for source in sources):
                            sources.append({"title": title, "url": url})

        return {
            "answer": answer or "No answer was returned.",
            "configured": True,
            "sources": sources[:8],
        }
