"""Module 6 multi-stock intelligence."""
from .contracts import MultiStockContext, MultiStockObservation, StockIntelligence
from .engine import MultiStockIntelligence
__all__ = ["MultiStockContext", "MultiStockObservation", "StockIntelligence", "MultiStockIntelligence"]
from .ranking import StockRank, StockRanking, rank_stocks
from .sector_rotation import SectorRotation, SectorRotationRow, build_sector_rotation
from .breadth import MarketBreadth, build_market_breadth
from .correlation import CorrelationMatrix, build_correlation_matrix
from .relative_strength import RelativeStrength, RelativeStrengthRow, build_relative_strength
from .liquidity import LiquiditySnapshot, build_liquidity_snapshot

from .portfolio import PortfolioContext, build_portfolio_context
from .cross_asset import CrossAssetContext, CrossAssetRow, build_cross_asset_context
from .decision_explanation import DecisionExplanation, DecisionExplanationItem, build_decision_explanation

__all__ += ["PortfolioContext", "build_portfolio_context", "CrossAssetContext", "CrossAssetRow", "build_cross_asset_context", "DecisionExplanation", "DecisionExplanationItem", "build_decision_explanation"]

from .explanation_audit import ExplanationAuditResult, audit_decision_explanation
from .scanner import StockScannerRow, StockScannerSnapshot, StockScannerStore
__all__ += [
    "ExplanationAuditResult",
    "audit_decision_explanation",
    "StockScannerRow",
    "StockScannerSnapshot",
    "StockScannerStore",
]
