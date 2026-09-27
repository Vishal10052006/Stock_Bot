"""Read-only UPSTOX production position evidence runner.

This module composes the existing production transport, adapter validation, and
reconciliation contracts. It never submits, modifies, or cancels orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from execution.adapters.upstox import UpstoxAdapterConfig, UpstoxBrokerAdapter
from execution.adapters.upstox_positions import fetch_upstox_positions
from execution.adapters.upstox_production_positions import (
    UpstoxProductionPositionClient,
)
from execution.certification import PositionEvidenceReport, build_position_evidence
from execution.engine import PositionSnapshot


@dataclass(frozen=True, slots=True)
class UpstoxPositionEvidenceRun:
    """Observed provider positions plus the canonical evidence result."""

    evidence: PositionEvidenceReport
    positions: tuple[PositionSnapshot, ...]

    @property
    def safe(self) -> bool:
        return self.evidence.safe


def run_upstox_position_evidence(
    access_token: str,
    local_positions: Iterable[PositionSnapshot] | None,
    *,
    timeout_seconds: float = 15.0,
) -> UpstoxPositionEvidenceRun:
    """Fetch read-only production positions and reconcile them with local state.

    The access token is supplied at runtime and is not included in the result.
    """
    client = UpstoxProductionPositionClient(
        access_token,
        timeout_seconds=timeout_seconds,
    )
    adapter = UpstoxBrokerAdapter(
        UpstoxAdapterConfig(
            api_base_url="https://api.upstox.com",
            enabled=True,
            position_provider=lambda: fetch_upstox_positions(client.get_positions),
        ),
        client=client,
    )
    positions = adapter.positions()
    evidence = build_position_evidence(
        "upstox-production",
        local_positions,
        positions,
    )
    return UpstoxPositionEvidenceRun(
        evidence=evidence,
        positions=positions,
    )


__all__ = ["UpstoxPositionEvidenceRun", "run_upstox_position_evidence"]
