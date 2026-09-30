class RuntimeMode(str, Enum):
    """Supported STOCK_BOT runtime modes."""

    CEO_DEMO = "ceo-demo"
    SHADOW = "shadow"
    PAPER = "paper"
    READINESS = "readiness"
    LIVE_PAPER = "live-paper"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Validated configuration for one CLI invocation."""

    mode: RuntimeMode
    symbol: str = "RELIANCE"
    candles: int = 1
    input_path: Path | None = None
    quantity: float = 1.0
    price_column: str = "close"
    confirm_live: bool = False
    model_artifact: Path | None = None
    model_sha256: str | None = None
    model_version: str = "phase9-logistic-v1"
    benchmark_symbol: str = "NIFTY50"
    session_id: str = "VIRTUAL-INTRADAY-001"
    initial_equity: float = 100_000.0
    max_candles: int | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.candles <= 0: