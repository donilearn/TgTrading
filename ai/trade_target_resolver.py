import logging

from models.modify_scope import ModifyScope
from models.signal import SignalAnalysis
from models.signal_type import SignalType
from models.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)

_MODIFY_TYPES = {SignalType.UPDATE, SignalType.CANCEL, SignalType.CLOSE}


def resolve_trade_targets(
    signal: SignalAnalysis,
    trading_snapshot: TradingSnapshot | None,
) -> SignalAnalysis:
    if signal.signal_type not in _MODIFY_TYPES or not trading_snapshot:
        return signal

    symbol = signal.symbol
    if not symbol:
        return signal

    positions = _positions_for_symbol(trading_snapshot, symbol)
    orders = _orders_for_symbol(trading_snapshot, symbol)

    signal.target_position_ids = _validate_ids(
        signal.target_position_ids,
        {position.id for position in positions},
    )
    signal.target_order_ids = _validate_ids(
        signal.target_order_ids,
        {order.id for order in orders},
    )

    signal = _auto_target_single_match(signal, positions, orders)
    signal = _infer_scope(signal, positions, orders)
    return signal


def _positions_for_symbol(snapshot: TradingSnapshot, symbol: str):
    return [position for position in snapshot.positions if position.symbol == symbol]


def _orders_for_symbol(snapshot: TradingSnapshot, symbol: str):
    return [order for order in snapshot.orders if order.symbol == symbol]


def _validate_ids(requested: list[str], valid_ids: set[str]) -> list[str]:
    if not requested:
        return []
    kept = [item_id for item_id in requested if item_id in valid_ids]
    if len(kept) != len(requested):
        logger.info(
            "Dropped invalid target ids: %s",
            [item_id for item_id in requested if item_id not in valid_ids],
        )
    return kept


def _auto_target_single_match(
    signal: SignalAnalysis,
    positions: list,
    orders: list,
) -> SignalAnalysis:
    if signal.signal_type in (SignalType.UPDATE, SignalType.CLOSE):
        if not signal.target_position_ids and len(positions) == 1:
            signal.target_position_ids = [positions[0].id]
            logger.info("Auto-target position #%s", positions[0].id)

    if signal.signal_type in (SignalType.UPDATE, SignalType.CANCEL):
        if not signal.target_order_ids and len(orders) == 1:
            signal.target_order_ids = [orders[0].id]
            logger.info("Auto-target order #%s", orders[0].id)

    return signal


def _infer_scope(
    signal: SignalAnalysis,
    positions: list,
    orders: list,
) -> SignalAnalysis:
    if signal.signal_type == SignalType.CLOSE:
        signal.modify_scope = ModifyScope.POSITIONS
        return signal

    if signal.signal_type == SignalType.CANCEL:
        signal.modify_scope = ModifyScope.ORDERS
        return signal

    if signal.modify_scope != ModifyScope.BOTH:
        return signal

    if positions and not orders:
        signal.modify_scope = ModifyScope.POSITIONS
    elif orders and not positions:
        signal.modify_scope = ModifyScope.ORDERS

    return signal
