"""Read-only desktop read models for Module 5 D01-D10.

The desktop layer composes existing STOCK_BOT contracts. These models never
create strategy/risk/safety/execution authority and never mutate upstream state.
""" 
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


def _get(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return str(value)
    if dt.tzinfo is None:
        return None
    return dt.isoformat()


def _finite(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result and abs(result) != float("inf") else default


def _json(value: Any) -> Any:
    if is_dataclass(value):
        return _json(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        try:
            return value.value
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _json(value.item())
        except Exception:
            pass
    return value


def _tuple_strings(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    return tuple(str(v) for v in values)


@dataclass(frozen=True, slots=True)
class MarketDashboardState:
    timestamp: str
    symbol: str | None
    session_state: str
    timeframe: str | None
    price: float | None
    candle: Mapping[str, Any]
    freshness_seconds: float | None
    pipeline_health: Mapping[str, Any]
    monitoring_readiness: str
    paper_state: str
    live_execution_state: str = "LOCKED"
    authority: str = "OBSERVATION_ONLY"

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class PredictionPanelState:
    timestamp: str | None
    symbol: str | None
    long_success: float | None
    short_success: float | None
    no_edge: float | None
    predicted_class: str | None
    model_version: str | None
    feature_version: str | None
    analysis_version: str | None
    prediction_timestamp: str | None
    horizon: str | None
    calibration_version: str | None
    provenance: Mapping[str, Any]
    status: str

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class ExplanationItem:
    source: str
    state: str
    reason: str
    timestamp: str | None
    details: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class ExplanationState:
    timestamp: str | None
    symbol: str | None
    state: str
    items: tuple[ExplanationItem, ...]
    provenance: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class ResearchEvidenceItem:
    evidence_id: str
    title: str
    source: str
    available_at: str | None
    published_at: str | None
    relevance: float | None
    context: str
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class ResearchPanelState:
    decision_timestamp: str | None
    items: tuple[ResearchEvidenceItem, ...]
    status: str
    causal_boundary: str = "available_at <= decision_timestamp"

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class ScreenObserverPanelState:
    observed_at: str | None
    capture_status: str
    target_window: Mapping[str, Any]
    chart_detected: bool
    chart_confidence: float | None
    ocr_status: str
    symbol: str | None
    timeframe: str | None
    indicators: tuple[str, ...]
    bullish_candles: int
    bearish_candles: int
    confidence: Mapping[str, Any]
    reconciliation_status: str
    validation_status: str
    authority: str = "OBSERVATION_ONLY"

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class DecisionTimelineEvent:
    event_id: str
    event_type: str
    timestamp: str
    symbol: str | None
    state: str | None
    source: str
    reason: str | None
    details: Mapping[str, Any] = field(default_factory=dict)
    sequence: int = 0

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class DecisionTimelineState:
    events: tuple[DecisionTimelineEvent, ...]
    status: str

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class ModelTelemetryState:
    timestamp: str | None
    model_version: str | None
    prediction_count: int
    metrics: Mapping[str, Any]
    alerts: tuple[str, ...]
    status: str
    authority: str = "OBSERVATION_ONLY"

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class RiskPanelState:
    timestamp: str | None
    status: str
    exposure: float | None
    position: Mapping[str, Any]
    limits: Mapping[str, Any]
    daily_loss: float | None
    kill_switch: str
    rejection_reason: str | None
    safety_state: str
    authority: str = "RISK_ENGINE"

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class PaperAccountState:
    timestamp: str | None
    cash: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    gross_exposure: float
    positions: tuple[Mapping[str, Any], ...]
    orders: tuple[Mapping[str, Any], ...]
    execution_state: str
    reconciliation_state: str
    session_statistics: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


@dataclass(frozen=True, slots=True)
class ReplayState:
    session_id: str | None
    events: tuple[DecisionTimelineEvent, ...]
    cursor: int = 0
    status: str = "PAUSED"
    live_mutation: bool = False

    def __post_init__(self) -> None:
        if self.cursor < 0 or self.cursor > len(self.events):
            raise ValueError("replay cursor out of range")
        if self.status not in {"PAUSED", "PLAYING", "COMPLETE"}:
            raise ValueError("invalid replay status")
        if self.live_mutation:
            raise ValueError("desktop replay must never mutate live state")

    @property
    def current(self) -> DecisionTimelineEvent | None:
        if self.cursor == 0 or not self.events:
            return None
        return self.events[self.cursor - 1]

    def step(self) -> "ReplayState":
        if self.cursor >= len(self.events):
            return ReplayState(self.session_id, self.events, len(self.events), "COMPLETE", False)
        next_cursor = self.cursor + 1
        return ReplayState(
            self.session_id,
            self.events,
            next_cursor,
            "COMPLETE" if next_cursor == len(self.events) else "PAUSED",
            False,
        )

    def resume(self) -> "ReplayState":
        return ReplayState(
            self.session_id,
            self.events,
            self.cursor,
            "COMPLETE" if self.cursor == len(self.events) else "PLAYING",
            False,
        )

    def pause(self) -> "ReplayState":
        return ReplayState(self.session_id, self.events, self.cursor, "PAUSED", False)

    def as_dict(self) -> dict[str, Any]:
        return _json(asdict(self))


def build_market_dashboard(
    *,
    market: Any = None,
    monitoring: Any = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    session_state: str | None = None,
    paper_state: str = "IDLE",
    observed_at: Any = None,
    now: datetime | None = None,
) -> MarketDashboardState:
    now = now or datetime.now(timezone.utc)
    timestamp = _iso(now) or now.isoformat()
    price = _finite(_get(market, "price", _get(market, "close")))
    candle = _get(market, "candle", {})
    observed = _get(market, "timestamp", observed_at)
    freshness = None
    observed_iso = _iso(observed)
    if observed_iso is not None:
        try:
            freshness = max(0.0, (now - datetime.fromisoformat(observed_iso)).total_seconds())
        except (TypeError, ValueError):
            freshness = None

    dashboard = monitoring.dashboard() if monitoring is not None and hasattr(monitoring, "dashboard") else {}
    health = dashboard.get("health", ()) if isinstance(dashboard, Mapping) else ()
    if session_state is None:
        session_state = str(_get(market, "session_state", "UNKNOWN"))
    readiness = "UNKNOWN"
    if monitoring is not None and hasattr(monitoring, "report"):
        report = monitoring.report()
        readiness = str(_get(report, "readiness", _get(report, "status", "UNKNOWN")))
    elif dashboard:
        readiness = "OBSERVED"

    return MarketDashboardState(
        timestamp=timestamp,
        symbol=(symbol or _get(market, "symbol")),
        session_state=session_state,
        timeframe=(timeframe or _get(market, "timeframe")),
        price=price,
        candle=_json(candle) if isinstance(candle, Mapping) else {"value": _json(candle)},
        freshness_seconds=freshness,
        pipeline_health={"health": _json(health), "alerts": _json(dashboard.get("alerts", ())) if isinstance(dashboard, Mapping) else []},
        monitoring_readiness=readiness,
        paper_state=paper_state,
        live_execution_state="LOCKED",
    )


def build_prediction_panel(prediction: Any = None) -> PredictionPanelState:
    if prediction is None:
        return PredictionPanelState(None, None, None, None, None, None, None, None, None, None, None, None, {}, "MISSING")
    probabilities = _get(prediction, "probabilities")
    long_p = _get(prediction, "long_probability")
    short_p = _get(prediction, "short_probability")
    no_edge = _get(prediction, "no_edge_probability")
    if probabilities is not None and hasattr(probabilities, "iloc"):
        row = probabilities.iloc[0]
        long_p, short_p, no_edge = row.get("LONG_SUCCESS"), row.get("SHORT_SUCCESS"), row.get("NO_EDGE")
    timestamp = _iso(_get(prediction, "timestamp"))
    values = [_finite(long_p), _finite(short_p), _finite(no_edge)]
    valid = all(v is not None and 0.0 <= v <= 1.0 for v in values) and abs(sum(values) - 1.0) <= 1e-6
    return PredictionPanelState(
        timestamp=timestamp,
        symbol=_get(prediction, "symbol"),
        long_success=values[0],
        short_success=values[1],
        no_edge=values[2],
        predicted_class=_get(prediction, "predicted_class"),
        model_version=_get(prediction, "model_version"),
        feature_version=_get(prediction, "feature_version"),
        analysis_version=_get(prediction, "analysis_version"),
        prediction_timestamp=timestamp,
        horizon=_get(prediction, "horizon"),
        calibration_version=_get(prediction, "calibration_version"),
        provenance=_json(_get(prediction, "provenance", {})),
        status="VALID" if valid else "INVALID",
    )


def build_explanation(decision_chain: Any = None) -> ExplanationState:
    """Adapt the authoritative Module 7 explanation contract for the desktop."""
    if decision_chain is None:
        return ExplanationState(None, None, "NO_EVIDENCE", (), {})

    from multi_stock.decision_explanation import (
        DecisionExplanation,
        build_decision_explanation,
    )
    from multi_stock.explanation_audit import audit_decision_explanation

    if isinstance(decision_chain, DecisionExplanation):
        explanation = decision_chain
    else:
        components = (
            "market", "analysis", "prediction", "research", "screen",
            "strategy", "risk", "safety", "execution",
        )
        has_pipeline = any(_get(decision_chain, name) is not None for name in components)
        if not has_pipeline:
            return ExplanationState(None, None, "NO_EVIDENCE", (), {})

        timestamp = _get(decision_chain, "timestamp")
        if timestamp is None:
            for name in components:
                candidate = _get(decision_chain, name)
                timestamp = _get(candidate, "timestamp") if candidate is not None else None
                if timestamp is not None:
                    break
        if timestamp is None:
            return ExplanationState(None, None, "INVALID", (), {
                "source": "module7_decision_explanation",
                "authority": "OBSERVATION_ONLY",
                "audit_reasons": ("EXPLANATION_TIMESTAMP_MISSING",),
            })

        symbol = _get(decision_chain, "symbol")
        if symbol is None:
            for name in components:
                candidate = _get(decision_chain, name)
                symbol = _get(candidate, "symbol") if candidate is not None else None
                if symbol:
                    break
        if not symbol:
            return ExplanationState(None, None, "INVALID", (), {
                "source": "module7_decision_explanation",
                "authority": "OBSERVATION_ONLY",
                "audit_reasons": ("EXPLANATION_SYMBOL_MISSING",),
            })

        explanation = build_decision_explanation(
            timestamp,
            symbol,
            market=_get(decision_chain, "market"),
            analysis=_get(decision_chain, "analysis"),
            prediction=_get(decision_chain, "prediction"),
            research=_get(decision_chain, "research"),
            screen=_get(decision_chain, "screen"),
            strategy=_get(decision_chain, "strategy"),
            risk=_get(decision_chain, "risk"),
            safety=_get(decision_chain, "safety"),
            execution=_get(decision_chain, "execution"),
        )

    audit = audit_decision_explanation(explanation, expected_symbol=explanation.symbol)
    items = tuple(
        ExplanationItem(
            source=item.source,
            state=item.status,
            reason=item.reason,
            timestamp=item.timestamp.isoformat(),
            details={"stage": item.stage},
        )
        for item in explanation.items
    )
    provenance = {
        "source": "module7_decision_explanation",
        "authority": explanation.authority,
        "audit_valid": audit.valid,
        "audit_reasons": audit.reasons,
    }
    state = explanation.outcome if audit.valid else "INVALID"
    return ExplanationState(
        timestamp=explanation.timestamp.isoformat(),
        symbol=explanation.symbol,
        state=state,
        items=items,
        provenance=provenance,
    )


def build_research_panel(evidence: Iterable[Any] = (), *, decision_timestamp: Any = None) -> ResearchPanelState:
    decision_iso = _iso(decision_timestamp)
    decision_dt = None
    if decision_iso:
        decision_dt = datetime.fromisoformat(decision_iso)
    items: list[ResearchEvidenceItem] = []
    rejected = 0
    for index, item in enumerate(evidence):
        available = _iso(_get(item, "available_at", _get(item, "timestamp")))
        if decision_dt is not None and available is not None:
            available_dt = datetime.fromisoformat(available)
            if available_dt > decision_dt:
                rejected += 1
                continue
        items.append(ResearchEvidenceItem(
            evidence_id=str(_get(item, "evidence_id", _get(item, "id", index))),
            title=str(_get(item, "title", _get(item, "headline", "Untitled evidence"))),
            source=str(_get(item, "source", _get(item, "publisher", "unknown"))),
            available_at=available,
            published_at=_iso(_get(item, "published_at")),
            relevance=_finite(_get(item, "relevance", _get(item, "score"))),
            context=str(_get(item, "context", _get(item, "summary", ""))),
            status="AVAILABLE",
            metadata=_json(_get(item, "metadata", {})),
        ))
    status = "FUTURE_EVIDENCE_REJECTED" if rejected and not items else ("AVAILABLE" if items else "NO_EVIDENCE")
    return ResearchPanelState(decision_iso, tuple(items), status)


def build_screen_panel(observation: Any = None, *, reconciliation: Any = None, validation: Any = None) -> ScreenObserverPanelState:
    if observation is None:
        return ScreenObserverPanelState(None, "UNAVAILABLE", {}, False, None, "UNAVAILABLE", None, None, (), 0, 0, {}, "INVALID", "INVALID")
    chart = _get(observation, "chart")
    confidence = _get(observation, "confidence")
    candles = _get(observation, "candles")
    target = _get(observation, "target_window")
    return ScreenObserverPanelState(
        observed_at=_iso(_get(observation, "observed_at")),
        capture_status="CAPTURED" if _get(observation, "image") is not None else "UNAVAILABLE",
        target_window=_json(target) if isinstance(target, Mapping) else _json(target) or {},
        chart_detected=bool(_get(chart, "detected", False)),
        chart_confidence=_finite(_get(chart, "confidence")),
        ocr_status=str(_get(_get(observation, "ocr_result"), "status", "UNAVAILABLE")),
        symbol=_get(observation, "symbol"),
        timeframe=_get(observation, "timeframe"),
        indicators=_tuple_strings(_get(observation, "indicators")),
        bullish_candles=int(_get(candles, "bullish", 0) or 0),
        bearish_candles=int(_get(candles, "bearish", 0) or 0),
        confidence=_json(confidence) if confidence is not None else {},
        reconciliation_status=str(_get(reconciliation, "status", "UNKNOWN")),
        validation_status="VALID" if validation is None else ("VALID" if bool(_get(validation, "valid", False)) else "INVALID"),
    )


def build_timeline(events: Iterable[Any] = ()) -> DecisionTimelineState:
    normalized: list[DecisionTimelineEvent] = []
    for index, event in enumerate(events):
        timestamp = _iso(_get(event, "timestamp", _get(event, "observed_at")))
        if timestamp is None:
            continue
        normalized.append(DecisionTimelineEvent(
            event_id=str(_get(event, "event_id", _get(event, "id", index))),
            event_type=str(_get(event, "event_type", _get(event, "type", "UNKNOWN"))),
            timestamp=timestamp,
            symbol=_get(event, "symbol"),
            state=_get(event, "state", _get(event, "status")),
            source=str(_get(event, "source", "unknown")),
            reason=_get(event, "reason"),
            details=_json(_get(event, "details", _get(event, "payload", {}))),
            sequence=index,
        ))
    normalized.sort(key=lambda e: (e.timestamp, e.sequence))
    renumbered = tuple(
        DecisionTimelineEvent(e.event_id, e.event_type, e.timestamp, e.symbol, e.state, e.source, e.reason, e.details, i)
        for i, e in enumerate(normalized)
    )
    return DecisionTimelineState(renumbered, "READY" if renumbered else "EMPTY")


def build_model_telemetry(monitoring: Any = None) -> ModelTelemetryState:
    dashboard = monitoring.dashboard() if monitoring is not None and hasattr(monitoring, "dashboard") else {}
    metrics = dashboard.get("metrics", {}) if isinstance(dashboard, Mapping) else {}
    alerts = dashboard.get("alerts", ()) if isinstance(dashboard, Mapping) else ()
    alert_codes = tuple(str(_get(a, "code", a)) for a in alerts)
    model_version = metrics.get("model.version") if isinstance(metrics, Mapping) else None
    count = int(metrics.get("model.prediction_count", 0) or 0) if isinstance(metrics, Mapping) else 0
    return ModelTelemetryState(
        timestamp=_get(dashboard, "timestamp"),
        model_version=model_version,
        prediction_count=count,
        metrics=_json(metrics),
        alerts=alert_codes,
        status="OBSERVED" if dashboard else "NO_TELEMETRY",
    )


def build_risk_panel(risk: Any = None, *, safety: Any = None) -> RiskPanelState:
    if risk is None:
        return RiskPanelState(None, "UNKNOWN", None, {}, {}, None, "UNKNOWN", "risk state unavailable", str(_get(safety, "status", "UNKNOWN")))
    status = str(_get(_get(risk, "decision"), "status", _get(risk, "status", "UNKNOWN")))
    reason = _get(_get(risk, "decision"), "reason", _get(risk, "reason"))
    exposure = _finite(_get(risk, "gross_exposure", _get(risk, "exposure")))
    daily_loss = _finite(_get(risk, "daily_loss"))
    return RiskPanelState(
        timestamp=_iso(_get(risk, "timestamp")),
        status=status,
        exposure=exposure,
        position=_json(_get(risk, "position", {})),
        limits=_json(_get(risk, "limits", {})),
        daily_loss=daily_loss,
        kill_switch=str(_get(risk, "kill_switch", "UNKNOWN")),
        rejection_reason=reason,
        safety_state=str(_get(safety, "status", _get(safety, "decision", "UNKNOWN"))),
    )


def build_paper_account(runtime: Any = None, *, prices: Mapping[str, float] | None = None, timestamp: Any = None) -> PaperAccountState:
    if runtime is None:
        return PaperAccountState(_iso(timestamp), 0.0, 0.0, 0.0, 0.0, 0.0, (), (), "IDLE", "UNKNOWN", {})
    prices = prices or {}
    equity, realized, unrealized, exposure = runtime.account_snapshot(dict(prices))
    positions = tuple(_json(p) for p in getattr(runtime, "positions", ()))
    orders = tuple(_json(o) for o in getattr(runtime, "journal", ()))
    cash = float(runtime.config.initial_equity) + float(realized)
    return PaperAccountState(
        timestamp=_iso(timestamp) or datetime.now(timezone.utc).isoformat(),
        cash=cash,
        equity=equity,
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        gross_exposure=exposure,
        positions=positions,
        orders=orders,
        execution_state="PAPER_ONLY",
        reconciliation_state="OBSERVED",
        session_statistics={"orders": len(orders), "open_positions": len(positions)},
    )


def start_replay(session_id: str | None, events: Sequence[Any]) -> ReplayState:
    timeline = build_timeline(events)
    return ReplayState(session_id, timeline.events)


__all__ = [
    "MarketDashboardState", "PredictionPanelState", "ExplanationItem", "ExplanationState",
    "ResearchEvidenceItem", "ResearchPanelState", "ScreenObserverPanelState",
    "DecisionTimelineEvent", "DecisionTimelineState", "ModelTelemetryState", "RiskPanelState",
    "PaperAccountState", "ReplayState", "build_market_dashboard", "build_prediction_panel",
    "build_explanation", "build_research_panel", "build_screen_panel", "build_timeline",
    "build_model_telemetry", "build_risk_panel", "build_paper_account", "start_replay",
]
