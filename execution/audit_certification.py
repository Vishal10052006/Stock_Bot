"""PAPER-05 execution journal and audit certification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
from execution.audit import DuplicateExecutionAuditError, ExecutionAuditRecord, ExecutionAuditStore
from execution.engine import ExecutionEngine
from execution.trading_execution import ExecutionAuthorization, ExecutionAuthorizationStatus
from trading.strategy.models import StrategyDirection

TS = pd.Timestamp("2026-09-27T10:00:00+05:30")


@dataclass(frozen=True, slots=True)
class AuditCertificationCase:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class AuditCertificationReport:
    cases: tuple[AuditCertificationCase, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def failed(self) -> tuple[AuditCertificationCase, ...]:
        return tuple(case for case in self.cases if not case.passed)


def _authorization(quantity: float = 100.0) -> ExecutionAuthorization:
    return ExecutionAuthorization(
        timestamp=TS,
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="PAPER-05 audit certification",
        risk_version="RISK-v1.0",
        approved_quantity=quantity,
        approved_notional=quantity * 100.0,
        risk_decision_id="paper05-risk",
    )


def _case(name: str, check) -> AuditCertificationCase:
    try:
        check()
    except Exception as exc:
        return AuditCertificationCase(name, False, f"{type(exc).__name__}: {exc}")
    return AuditCertificationCase(name, True, "PASS")


def run_audit_certification() -> AuditCertificationReport:
    """Certify durable order/event/fill/position audit lineage."""

    def decision_order_fill_position_lineage():
        with TemporaryDirectory() as directory:
            store = ExecutionAuditStore(Path(directory) / "execution-audit.jsonl")
            adapter = PaperBrokerAdapter(
                config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
                price_provider=lambda _order: 100.0,
            )
            engine = ExecutionEngine(adapter, audit_store=store)
            auth = _authorization()
            request = ExecutionEngine.from_authorization(
                auth,
                decision_id="paper05-lineage",
            )
            result = engine.submit(request)
            assert result.filled

            records = store.read_all()
            types = [record.record_type for record in records]
            assert types[:3] == ["EVENT", "EVENT", "EVENT"]
            assert "ORDER" in types
            assert "FILL" in types
            assert "POSITION" in types
            assert all(record.client_order_id == request.client_order_id for record in records)
            assert all(record.decision_id == request.decision_id for record in records)

            order_record = next(record for record in records if record.record_type == "ORDER")
            fill_record = next(record for record in records if record.record_type == "FILL")
            position_record = next(record for record in records if record.record_type == "POSITION")
            assert order_record.payload["order"]["decision_id"] == request.decision_id
            assert fill_record.payload["client_order_id"] == request.client_order_id
            assert position_record.payload["symbol"] == "ITC"
            assert position_record.payload["quantity"] == 100.0

    def lifecycle_events_are_durable():
        with TemporaryDirectory() as directory:
            store = ExecutionAuditStore(Path(directory) / "events.jsonl")
            engine = ExecutionEngine(PaperBrokerAdapter(), audit_store=store)
            engine.submit(
                ExecutionEngine.from_authorization(
                    _authorization(),
                    decision_id="paper05-events",
                )
            )
            event_records = [r for r in store.read_all() if r.record_type == "EVENT"]
            assert [r.payload["to_status"] for r in event_records] == [
                "VALIDATED",
                "SUBMITTING",
                "FILLED",
            ]

    def duplicate_audit_identity_is_rejected():
        with TemporaryDirectory() as directory:
            store = ExecutionAuditStore(Path(directory) / "audit.jsonl")
            record = ExecutionAuditRecord(
                record_id="EA-fixed",
                record_type="EVENT",
                timestamp=TS,
                client_order_id="SB-fixed",
                decision_id="decision-fixed",
                purpose="ENTRY",
                payload={"to_status": "FILLED"},
            )
            store.append(record)
            try:
                store.append(record)
            except DuplicateExecutionAuditError:
                return
            raise AssertionError("duplicate audit record was accepted")

    def audit_survives_restart():
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            store = ExecutionAuditStore(path)
            adapter = PaperBrokerAdapter()
            engine = ExecutionEngine(adapter, audit_store=store)
            engine.submit(
                ExecutionEngine.from_authorization(
                    _authorization(),
                    decision_id="paper05-restart",
                )
            )
            before = store.read_all()

            restarted_store = ExecutionAuditStore(path)
            after = restarted_store.read_all()
            assert after == before
            assert len(after) >= 6

    def malformed_audit_fails_closed():
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            path.write_text('{"record_type":"EVENT"}\n', encoding="utf-8")
            try:
                ExecutionAuditStore(path).read_all()
            except ValueError as exc:
                assert "invalid execution audit record" in str(exc)
                return
            raise AssertionError("malformed audit record was accepted")

    cases = (
        _case("decision_order_fill_position_lineage", decision_order_fill_position_lineage),
        _case("lifecycle_events_are_durable", lifecycle_events_are_durable),
        _case("duplicate_audit_identity_is_rejected", duplicate_audit_identity_is_rejected),
        _case("audit_survives_restart", audit_survives_restart),
        _case("malformed_audit_fails_closed", malformed_audit_fails_closed),
    )
    return AuditCertificationReport(cases)


__all__ = ["AuditCertificationCase", "AuditCertificationReport", "run_audit_certification"]
