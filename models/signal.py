from enum import Enum

from pydantic import BaseModel, Field

from models.entry_level import EntryLevel
from models.modify_scope import ModifyScope
from models.order_type import OrderType
from models.signal_type import SignalType
from models.take_profit_level import TakeProfitLevel


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    NONE = "none"


class SignalAnalysis(BaseModel):
    is_signal: bool = Field(
        description="Whether the message contains a valid trading signal",
    )
    signal_type: SignalType = SignalType.NONE
    action: TradeAction = TradeAction.NONE
    order_type: OrderType = OrderType.MARKET
    symbol: str | None = Field(
        default=None,
        description="Trading pair e.g. EURUSD, XAUUSD",
    )
    volume: float | None = Field(
        default=None,
        description="Total lot size if specified in the message",
    )
    entry_price: float | None = Field(
        default=None,
        description="Single entry price for market/limit/stop orders",
    )
    entry_zone_low: float | None = Field(
        default=None,
        description="Lower bound of entry zone price range (e.g. 64300)",
    )
    entry_zone_high: float | None = Field(
        default=None,
        description="Upper bound of entry zone price range (e.g. 64400)",
    )
    entry_levels: list[EntryLevel] = Field(
        default_factory=list,
        description="Multiple entry levels (e.g. Entry 1, Entry 2)",
    )
    stop_loss: float | None = Field(
        default=None,
        description="Absolute stop loss PRICE level only (e.g. 104500, 1.0850). Never put pip counts here.",
    )
    take_profits: list[TakeProfitLevel] = Field(
        default_factory=list,
        description="Take profit absolute PRICE levels. Never put pip counts here.",
    )
    stop_limit_price: float | None = Field(
        default=None,
        description="Stop limit price for stop_limit order type",
    )
    sl_pips: float | None = Field(
        default=None,
        description="Stop loss distance in pips from entry/current price. Use for 'stop X pips', 'SL 1000 pips'.",
    )
    tp_pips: float | None = Field(
        default=None,
        description="Take profit distance in pips from entry/current price. Use for 'TP X pips', 'take X pips'.",
    )
    breakeven_sl: bool = Field(
        default=False,
        description="True to move SL to each targeted position/order open price (breakeven).",
    )
    modify_scope: ModifyScope = Field(
        default=ModifyScope.BOTH,
        description="UPDATE scope: positions=open market trades, orders=pending limit/stop, both=all.",
    )
    target_position_ids: list[str] = Field(
        default_factory=list,
        description="Specific open position ids from account metadata. Empty = all matching symbol.",
    )
    target_order_ids: list[str] = Field(
        default_factory=list,
        description="Specific pending order ids from account metadata. Empty = all matching symbol.",
    )
    is_re_entry: bool = Field(
        default=False,
        description="True if this is a re-entry signal",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Certainty 0-1. Use >= 0.9 when is_signal=true and intent is clear.",
    )
    reasoning: str = Field(default="")

    @property
    def primary_take_profit(self) -> float | None:
        if not self.take_profits:
            return None
        sorted_tps = sorted(self.take_profits, key=lambda tp: tp.level)
        return sorted_tps[0].price

    @property
    def is_actionable(self) -> bool:
        if not self.is_signal or self.confidence < 0.7:
            return False

        if self.signal_type == SignalType.UPDATE:
            return self.symbol is not None and (
                self.breakeven_sl
                or self.stop_loss is not None
                or self.primary_take_profit is not None
                or len(self.take_profits) > 0
                or self.sl_pips is not None
                or self.tp_pips is not None
            )

        if self.signal_type == SignalType.CANCEL:
            return self.symbol is not None or len(self.target_order_ids) > 0

        if self.signal_type == SignalType.CLOSE:
            return self.symbol is not None or len(self.target_position_ids) > 0

        if not self.symbol:
            return False

        if self.signal_type not in (SignalType.ENTRY, SignalType.RE_ENTRY):
            return False

        if self.action == TradeAction.NONE:
            return False

        if self.order_type == OrderType.MARKET:
            return True

        if self.entry_zone_low is not None and self.entry_zone_high is not None:
            return True

        return self.entry_price is not None or len(self.entry_levels) > 0
