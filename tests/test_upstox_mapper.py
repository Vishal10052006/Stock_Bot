"""Unit tests for the Upstox instrument mapping boundary."""

import pytest

from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)


def test_mapper_normalizes_symbols():
    """Internal symbols should be normalized while retaining provider IDs."""
    mapper = UpstoxInstrumentMapper(
        {" reliance ": "NSE_EQ|123", "tcs": "NSE_EQ|456"}
    )

    assert mapper.instrument_key("RELIANCE") == "NSE_EQ|123"
    assert mapper.instrument_key(" tcs ") == "NSE_EQ|456"
    assert mapper.symbols() == ("RELIANCE", "TCS")


def test_mapper_rejects_unknown_symbol():
    """Unknown symbols must fail explicitly instead of guessing identifiers."""
    mapper = UpstoxInstrumentMapper({"RELIANCE": "NSE_EQ|123"})

    with pytest.raises(KeyError, match="No Upstox instrument key"):
        mapper.instrument_key("INFY")


def test_mapper_requires_at_least_one_valid_mapping():
    """An empty mapping cannot support deterministic subscriptions."""
    with pytest.raises(ValueError, match="valid instrument mapping"):
        UpstoxInstrumentMapper({"": ""})


def test_mapper_returns_provider_identity():
    """Identity should contain normalized symbol and provider instrument key."""
    mapper = UpstoxInstrumentMapper(
        {
            " reliance ": " NSE_EQ|123 ",
        }
    )

    identity = mapper.identity(" RELIANCE ")

    assert identity.symbol == "RELIANCE"
    assert identity.instrument_key == "NSE_EQ|123"
    assert identity.isin == "123"


def test_mapper_identity_rejects_malformed_nse_equity_key():
    """Malformed NSE equity keys must not produce an invalid ISIN."""
    mapper = UpstoxInstrumentMapper(
        {"RELIANCE": "NSE_EQ|"}
    )

    with pytest.raises(
        ValueError,
        match="NSE equity instrument key",
    ):
        mapper.identity("RELIANCE")


def test_mapper_identity_rejects_unknown_symbol():
    """Identity lookup must fail rather than guess an identifier."""
    mapper = UpstoxInstrumentMapper(
        {"RELIANCE": "NSE_EQ|123"}
    )

    with pytest.raises(KeyError, match="No Upstox instrument key"):
        mapper.identity("INFY")
