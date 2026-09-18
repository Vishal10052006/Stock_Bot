from pathlib import Path


SPEC = Path("TRADING_SPECIFICATION.md")


def test_trading_specification_exists():
    assert SPEC.is_file()


def test_trading_specification_contains_required_market_contract():
    source = SPEC.read_text().lower()

    required = [
        "nse",
        "equity cash",
        "5-minute candles",
        "09:15–15:30 ist",
        "₹100,000",
        "0.5%",
        "1.5%",
        "maximum trades per day",
        "maximum open positions",
        "75%",
        "long",
        "short",
        "no trade",
        "60 minutes",
        "1.5r",
        "transaction costs",
        "slippage",
        "live trading lock",
        "frozen for initial research/paper configuration",
    ]

    for item in required:
        assert item in source, f"Missing specification requirement: {item}"


def test_trading_specification_preserves_risk_authority():
    source = SPEC.read_text()

    assert "The risk engine has veto authority" in source
    assert "A strategy/model cannot override" in source


def test_trading_specification_preserves_causality():
    source = SPEC.read_text()

    assert "Every trading feature and decision input must use only information" in source
    assert "Future information must never enter" in source


def test_trading_specification_keeps_live_execution_locked():
    source = SPEC.read_text()

    assert "Live trading is LOCKED." in source
    assert "Live activation requires all required validation and safety gates." in source


def test_trading_specification_forbids_fabricated_market_context():
    source = SPEC.read_text()

    assert "must never fabricate market or sector values" in source
