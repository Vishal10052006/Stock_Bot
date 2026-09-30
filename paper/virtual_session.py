    initial_equity: float = 100_000.0
    output_dir: Path = Path("paper/virtual_sessions")
    session_id: str = "VIRTUAL-INTRADAY-001"
    market_timezone: str = "Asia/Kolkata"
    session_open: str = "09:15"
    session_close: str = "15:30"

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.initial_equity)) or self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive and finite")
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if not self.market_timezone.strip():
            raise ValueError("market_timezone must not be empty")
        for name, value in (
            ("session_open", self.session_open),
            ("session_close", self.session_close),
        ):
            if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is None:
                raise ValueError(f"{name} must use HH:MM format")
        if self.session_open >= self.session_close:
            raise ValueError("session_open must be earlier than session_close")


class VirtualIntradaySession:
    """Run the canonical trading pipeline against a virtual account.

    All trading decisions and paper fills remain owned by the existing
    canonical orchestrator and LivePaperEngine. This class adds only the
    full-session account boundary and auditable account ledger.