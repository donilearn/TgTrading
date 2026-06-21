import logging

from models.chat_message import ChatMessage
from models.modify_scope import ModifyScope
from models.signal import SignalAnalysis
from models.signal_type import SignalType
from models.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)

_BREAKEVEN_HINTS = (
    "breakeven",
    "break even",
    "secure profit",
    "secure the trade",
    "entry price",
    "open price",
    "profitni qop",
    "foydani qop",
    "xavfsiz",
    "be ",
    "nolga",
    "kirish narx",
)


def resolve_update_signal(
    signal: SignalAnalysis,
    message: ChatMessage,
    trading_snapshot: TradingSnapshot | None,
) -> SignalAnalysis:
    if signal.signal_type != SignalType.UPDATE:
        return normalize_confidence(signal)

    signal = _resolve_breakeven_stop(signal, message, trading_snapshot)
    signal = _move_entry_price_to_stop_loss(signal)
    return normalize_confidence(signal)


def normalize_confidence(signal: SignalAnalysis) -> SignalAnalysis:
    if not signal.is_signal or signal.confidence >= 0.7:
        return signal

    if _has_actionable_payload(signal):
        signal.confidence = 0.85
        logger.info("Corrected: confidence raised to %.2f", signal.confidence)

    return signal


def _move_entry_price_to_stop_loss(signal: SignalAnalysis) -> SignalAnalysis:
    if signal.breakeven_sl or signal.stop_loss is not None or signal.entry_price is None:
        return signal

    signal.stop_loss = signal.entry_price
    signal.entry_price = None
    logger.info("Corrected: moved entry_price to stop_loss for UPDATE")
    return signal


def _resolve_breakeven_stop(
    signal: SignalAnalysis,
    message: ChatMessage,
    trading_snapshot: TradingSnapshot | None,
) -> SignalAnalysis:
    if signal.breakeven_sl:
        return signal
    if signal.stop_loss is not None or signal.sl_pips is not None:
        return signal
    if not trading_snapshot or not signal.symbol:
        return signal

    combined = f"{message.text or ''} {signal.reasoning}".lower()
    if not any(hint in combined for hint in _BREAKEVEN_HINTS):
        return signal

    positions = [
        position for position in trading_snapshot.positions
        if position.symbol == signal.symbol
    ]
    orders = [
        order for order in trading_snapshot.orders
        if order.symbol == signal.symbol
    ]

    if not positions and not orders:
        return signal

    signal.breakeven_sl = True
    signal.stop_loss = None
    signal.entry_price = None
    signal.is_signal = True

    if positions and not orders:
        signal.modify_scope = ModifyScope.POSITIONS
    elif orders and not positions:
        signal.modify_scope = ModifyScope.ORDERS

    logger.info(
        "Breakeven enabled for %s: %d position(s), %d order(s), scope=%s",
        signal.symbol,
        len(positions),
        len(orders),
        signal.modify_scope.value,
    )
    return signal


def _has_actionable_payload(signal: SignalAnalysis) -> bool:
    if not signal.is_signal:
        return False

    if signal.signal_type == SignalType.UPDATE:
        return signal.symbol is not None and (
            signal.breakeven_sl
            or signal.stop_loss is not None
            or signal.primary_take_profit is not None
            or len(signal.take_profits) > 0
            or signal.sl_pips is not None
            or signal.tp_pips is not None
        )

    if signal.signal_type == SignalType.CANCEL:
        return signal.symbol is not None or len(signal.target_order_ids) > 0

    if signal.signal_type == SignalType.CLOSE:
        return signal.symbol is not None or len(signal.target_position_ids) > 0

    if not signal.symbol:
        return False

    if signal.signal_type not in (SignalType.ENTRY, SignalType.RE_ENTRY):
        return False

    from models.signal import TradeAction
    from models.order_type import OrderType

    if signal.action == TradeAction.NONE:
        return False

    if signal.order_type == OrderType.MARKET:
        return True

    return signal.entry_price is not None or len(signal.entry_levels) > 0
