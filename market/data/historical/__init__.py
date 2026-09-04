"""Historical market-data contracts and infrastructure."""

from market.data.historical.calendar import (
    FixedSessionCalendar,
    MarketSessionCalendar,
    TradingSession,
)
from market.data.historical.models import (
    HistoricalDataRequest,
    HistoricalDataset,
)
from market.data.historical.nse_calendar import (
    NSETradingCalendar,
)
from market.data.historical.validation import (
    DatasetValidationResult,
    HistoricalDatasetValidator,
)
from market.data.historical.providers import (
    HistoricalDataPurpose,
    HistoricalMarketDataProvider,
    HistoricalProviderRole,
    StaticHistoricalMarketDataProvider,
)

__all__ = [
    "FixedSessionCalendar",
    "HistoricalDataRequest",
    "HistoricalDataset",
    "DatasetValidationResult",
    "HistoricalDatasetValidator",
    "HistoricalDataPurpose",
    "HistoricalMarketDataProvider",
    "HistoricalProviderRole",
    "MarketSessionCalendar",
    "NSETradingCalendar",
    "StaticHistoricalMarketDataProvider",
    "TradingSession",
]

from market.data.historical.storage import (
    HistoricalDatasetStore,
    JsonHistoricalDatasetStore,
)

__all__ += [
    "HistoricalDatasetStore",
    "JsonHistoricalDatasetStore",
]

from market.data.historical.pipeline import (
    HistoricalMarketDataPipeline,
    HistoricalPipelineResult,
)

__all__ += [
    "HistoricalMarketDataPipeline",
    "HistoricalPipelineResult",
]
