import pytest
from execution.instruments import Instrument, StaticInstrumentResolver

def test_static_resolver_returns_provider_identity():
    resolver = StaticInstrumentResolver((Instrument("ITC","NSE","NSE_EQ|INE154A01025",0.05),))
    item = resolver.resolve("itc")
    assert item.instrument_token == "NSE_EQ|INE154A01025"

def test_unknown_symbol_fails_closed():
    resolver = StaticInstrumentResolver(())
    with pytest.raises(KeyError):
        resolver.resolve("ITC")

def test_duplicate_symbol_rejected():
    item = Instrument("ITC","NSE","TOKEN",0.05)
    with pytest.raises(ValueError):
        StaticInstrumentResolver((item,item))
