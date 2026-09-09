"""Historical market-data provider adapters."""

from market.data.historical.adapters.yfinance import (
    YFinanceHistoricalMarketDataProvider,
)

__all__ = [
    "YFinanceHistoricalMarketDataProvider",
]

from market.data.historical.adapters.upstox import (
    UpstoxHistoricalDataError,
    UpstoxHistoricalMarketDataProvider,
)

__all__ = [
    "UpstoxHistoricalDataError",
    "UpstoxHistoricalMarketDataProvider",
]


from market.data.historical.adapters.nse_security import (
    NSESecurityDataError,
    NSESecurityWiseAdapter,
)

__all__ += [
    "NSESecurityDataError",
    "NSESecurityWiseAdapter",
]

from market.data.historical.adapters.nse_security_master import (
    NSESecurityMasterAdapter,
    NSESecurityMasterDataError,
)

__all__ += [
    "NSESecurityMasterAdapter",
    "NSESecurityMasterDataError",
]
