"""MB-22 compatibility."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class MarketBotVersion:
    bot:str="market-bot"; major:int=1; minor:int=0; patch:int=0
    @property
    def value(self): return f"{self.bot}-v{self.major}.{self.minor}.{self.patch}"
def assert_compatible(version,major=1):
    if not str(version).startswith(f"market-bot-v{major}."): raise ValueError(f"incompatible Market Bot version: {version}")
