            slippage_bps=self.config.slippage_bps,
            initial_equity=self.config.initial_equity,
        )
        self.runtime = PaperTradingRuntime(config=adapter_config)
        self.exit_engine = PaperExitEngine(
            fee_bps=self.config.fee_bps,
            slippage_bps=self.config.slippage_bps,
            session_cutoff_time=self.config.session_cutoff_time,
        )
        self.strategy_engine = StrategyEngine(strategy_config)
        self.risk_engine = RiskEngine(risk_config)
        self.safety_gate = IndependentSafetyGate()

        self._candle_history: list[dict[str, Any]] = []
        self._decisions: list[dict[str, Any]] = []
        self._submitted_orders: list[PaperOrder] = []
        self._session_completed = False
        self._start_time: pd.Timestamp | None = None
        self._last_time: pd.Timestamp | None = None

    @property
    def session_completed(self) -> bool:
        """True when target completed trades have been reached."""
        return self._session_completed

    @property
    def completed_count(self) -> int:
        """Number of closed trades produced so far."""
        return len(self.exit_engine.completed_outcomes)

    @property
    def submitted_order_count(self) -> int:
        """Number of filled paper entry orders submitted in this session."""
        return len(self._submitted_orders)

    def register_submitted_order(self, order: Any) -> None:
        """Register one filled paper order with the session controller."""
        if not isinstance(order, PaperOrder):
            raise TypeError("order must be a PaperOrder")
        if order.status is not PaperOrderStatus.FILLED:
            raise ValueError("only FILLED paper orders may be registered")
        self._submitted_orders.append(order)

    def observe_candle(self, candle: Any) -> list[TradeOutcome]:
        """Record one completed candle and process existing positions only.

        This is the canonical lifecycle hook for external Strategy/Risk
        orchestrators. It intentionally does not evaluate new entries.
        """
        raw_symbol = getattr(candle, "symbol", None) or candle["symbol"]
        symbol = str(raw_symbol).strip().upper()
        if symbol != self.config.symbol:
            return []

        raw_ts = getattr(candle, "timestamp", None) or candle["timestamp"]
        timestamp = pd.Timestamp(raw_ts)

        candle_dict = {
            "timestamp": timestamp,
            "symbol": symbol,
            "open": float(getattr(candle, "open", None) if hasattr(candle, "open") else candle["open"]),
            "high": float(getattr(candle, "high", None) if hasattr(candle, "high") else candle["high"]),
            "low": float(getattr(candle, "low", None) if hasattr(candle, "low") else candle["low"]),
            "close": float(getattr(candle, "close", None) if hasattr(candle, "close") else candle["close"]),
            "volume": float(getattr(candle, "volume", None) if hasattr(candle, "volume") else candle.get("volume", 1000.0)),
        }

        if self._start_time is None:
            self._start_time = timestamp
        self._last_time = timestamp
        self._candle_history.append(candle_dict)
        return self.exit_engine.process_candle(candle_dict)

    def on_candle(self, candle: Any) -> list[TradeOutcome]:
        """Process one closed 5-minute candle through the complete trading loop."""
        raw_symbol = getattr(candle, "symbol", None) or candle["symbol"]
        symbol = str(raw_symbol).strip().upper()
        if symbol != self.config.symbol:
            return []

        raw_ts = getattr(candle, "timestamp", None) or candle["timestamp"]
        timestamp = pd.Timestamp(raw_ts)

        open_p = float(getattr(candle, "open", None) if hasattr(candle, "open") else candle["open"])
        high_p = float(getattr(candle, "high", None) if hasattr(candle, "high") else candle["high"])
        low_p = float(getattr(candle, "low", None) if hasattr(candle, "low") else candle["low"])
        close_p = float(getattr(candle, "close", None) if hasattr(candle, "close") else candle["close"])
        vol = float(getattr(candle, "volume", None) if hasattr(candle, "volume") else candle.get("volume", 1000.0))

        candle_dict = {
            "timestamp": timestamp,
            "symbol": symbol,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": vol,
        }

        if self._start_time is None:
            self._start_time = timestamp