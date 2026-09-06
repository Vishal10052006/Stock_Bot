"""Tests for historical provider policy boundaries."""

import pytest

from market.data.historical.adapters.yfinance import (
    YFinanceHistoricalMarketDataProvider,
)
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.pipeline import HistoricalMarketDataPipeline
from market.data.historical.providers import (
    HistoricalDataPurpose,
    HistoricalProviderRole,
    StaticHistoricalMarketDataProvider,
)


def test_yfinance_provider_is_research_only() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    assert provider.role is HistoricalProviderRole.RESEARCH
    assert provider.period == "5d"
    assert provider.auto_adjust is False


def test_yfinance_supports_canonical_five_minute_request() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    assert provider._interval(request.timeframe_minutes) == "5m"


def test_static_provider_is_test_only() -> None:
    assert (
        StaticHistoricalMarketDataProvider.role
        is HistoricalProviderRole.TEST
    )


def test_research_purpose_accepts_research_provider() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        require_complete_sessions=False,
        purpose=HistoricalDataPurpose.RESEARCH,
    )

    assert pipeline._purpose is HistoricalDataPurpose.RESEARCH


def test_authoritative_purpose_rejects_research_provider_before_fetch() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        purpose=HistoricalDataPurpose.CANONICAL,
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with pytest.raises(
        ValueError,
        match="canonical historical ingestion requires a canonical provider",
    ):
        pipeline.ingest(request)


def test_authoritative_purpose_rejects_test_provider_before_fetch() -> None:
    provider = StaticHistoricalMarketDataProvider([])

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        purpose=HistoricalDataPurpose.CANONICAL,
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with pytest.raises(
        ValueError,
        match="canonical historical ingestion requires a canonical provider",
    ):
        pipeline.ingest(request)


def test_upstox_provenance_contains_provider_identity():
    from market.data.historical.adapters.upstox import (
        UpstoxHistoricalMarketDataProvider,
    )
    from market.data.historical.models import HistoricalDataRequest
    from market.data.ingestion.providers.upstox.instrument_mapper import (
        UpstoxInstrumentMapper,
    )

    provider = UpstoxHistoricalMarketDataProvider(
        "test-access-token",
        UpstoxInstrumentMapper(
            {"RELIANCE": "NSE_EQ|INE002A01018"}
        ),
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    assert provider.provenance(request) == {
        "provider": "upstox",
        "instrument_key": "NSE_EQ|INE002A01018",
    }


def test_yfinance_provenance_records_provider_symbol_and_adjustment():
    from market.data.historical.adapters.yfinance import (
        YFinanceHistoricalMarketDataProvider,
    )
    from market.data.historical.models import HistoricalDataRequest

    provider = YFinanceHistoricalMarketDataProvider(
        auto_adjust=False,
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    assert provider.provenance(request) == {
        "provider": "yfinance",
        "provider_symbol": "RELIANCE.NS",
        "adjustment_policy": "unadjusted",
    }


def test_upstox_index_provenance_accepts_nse_index_instrument():
    from market.data.historical.adapters.upstox import (
        UpstoxHistoricalMarketDataProvider,
    )
    from market.data.ingestion.providers.upstox.instrument_mapper import (
        UpstoxInstrumentMapper,
    )

    provider = UpstoxHistoricalMarketDataProvider(
        "test-access-token",
        UpstoxInstrumentMapper(
            {"NIFTY50": "NSE_INDEX|Nifty 50"}
        ),
    )

    request = HistoricalDataRequest(
        symbol="NIFTY50",
        exchange="NSE",
        timeframe_minutes=5,
    )

    assert provider.provenance(request) == {
        "provider": "upstox",
        "instrument_key": "NSE_INDEX|Nifty 50",
    }


def test_instrument_lifecycle_provider_protocol_contract() -> None:
    from datetime import date

    from market.data.historical.instrument_status import (
        InstrumentStatus,
        InstrumentStatusTimeline,
        InstrumentStatusType,
    )
    from market.data.historical.providers import (
        InstrumentLifecycleProvider,
    )

    class LifecycleFixture:
        def get_status_timeline(
            self,
            symbol: str,
        ) -> InstrumentStatusTimeline:
            return InstrumentStatusTimeline(
                statuses=(
                    InstrumentStatus(
                        symbol=symbol,
                        status=InstrumentStatusType.ACTIVE,
                        effective_from=date(2026, 1, 1),
                    ),
                ),
            )

    provider = LifecycleFixture()

    assert isinstance(provider, InstrumentLifecycleProvider)

    timeline = provider.get_status_timeline("RELIANCE")

    assert timeline.symbol == "RELIANCE"
    assert timeline.status_on(date(2026, 1, 2)) is InstrumentStatusType.ACTIVE


def test_instrument_universe_provider_protocol_contract() -> None:
    from datetime import date

    from market.data.historical.providers import (
        InstrumentUniverseProvider,
    )
    from market.data.historical.universe import (
        UniverseMembership,
        UniverseMembershipTimeline,
    )

    class UniverseFixture:
        def get_membership_timeline(
            self,
            symbol: str,
            exchange: str,
        ) -> UniverseMembershipTimeline:
            return UniverseMembershipTimeline(
                memberships=(
                    UniverseMembership(
                        symbol=symbol,
                        exchange=exchange,
                        effective_from=date(2026, 1, 1),
                    ),
                ),
            )

    provider = UniverseFixture()

    assert isinstance(provider, InstrumentUniverseProvider)

    timeline = provider.get_membership_timeline(
        "RELIANCE",
        "NSE",
    )

    assert timeline.is_member(
        symbol="RELIANCE",
        exchange="NSE",
        as_of=date(2026, 1, 2),
    )


def test_instrument_symbol_history_provider_protocol_contract() -> None:
    from datetime import date

    from market.data.historical.providers import (
        InstrumentSymbolHistoryProvider,
    )
    from market.data.historical.symbol_history import (
        InstrumentSymbolInterval,
        InstrumentSymbolTimeline,
    )

    class SymbolHistoryFixture:
        def get_symbol_timeline(
            self,
            isin: str,
            exchange: str,
        ) -> InstrumentSymbolTimeline:
            return InstrumentSymbolTimeline(
                intervals=(
                    InstrumentSymbolInterval(
                        isin=isin,
                        symbol="OLDNAME",
                        exchange=exchange,
                        effective_from=date(2020, 1, 1),
                    ),
                ),
            )

    provider = SymbolHistoryFixture()

    assert isinstance(provider, InstrumentSymbolHistoryProvider)

    timeline = provider.get_symbol_timeline(
        "INE000A01000",
        "NSE",
    )

    assert timeline.isin == "INE000A01000"
    assert timeline.symbol_on(date(2020, 1, 2)) == "OLDNAME"


def test_security_lineage_provider_protocol_contract() -> None:
    from datetime import date

    from market.data.historical.providers import (
        SecurityLineageProvider,
    )
    from market.data.historical.security_lineage import (
        SecurityLineage,
        SecurityLineageObservation,
    )

    class SecurityLineageFixture:
        def get_security_lineage(
            self,
            observation: SecurityLineageObservation,
        ) -> SecurityLineage:
            return SecurityLineage(
                lineage_id="TEST-LINEAGE",
                observations=(observation,),
            )

    observation = SecurityLineageObservation(
        fin_instrm_id="3072",
        symbol="SHALMPAINT",
        series="EQ",
        isin="INE849C01026",
        exchange="NSE",
        effective_from=date(2008, 1, 1),
        source="test",
    )

    provider = SecurityLineageFixture()

    assert isinstance(provider, SecurityLineageProvider)

    lineage = provider.get_security_lineage(observation)

    assert lineage.lineage_id == "TEST-LINEAGE"
    assert lineage.observation_on(date(2008, 1, 2)) == observation
