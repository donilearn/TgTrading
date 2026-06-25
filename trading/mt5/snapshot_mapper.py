from typing import Any

import MetaTrader5 as mt5

from trading.trading_snapshot import TradingSnapshot


class SnapshotMapper:
    @staticmethod
    def from_mt5(positions: tuple, orders: tuple) -> TradingSnapshot:
        return TradingSnapshot(
            positions=[_map_position(item) for item in positions],
            orders=[_map_order(item) for item in orders],
        )


def _map_position(position: Any) -> dict[str, Any]:
    side = (
        "POSITION_TYPE_BUY"
        if position.type == mt5.POSITION_TYPE_BUY
        else "POSITION_TYPE_SELL"
    )
    return {
        "id": str(position.ticket),
        "magic": position.magic,
        "label": str(position.magic),
        "symbol": position.symbol,
        "type": side,
        "openPrice": position.price_open,
        "volume": position.volume,
        "stopLoss": _optional_price(position.sl),
        "takeProfit": _optional_price(position.tp),
        "openTime": position.time,
    }


def _map_order(order: Any) -> dict[str, Any]:
    return {
        "id": str(order.ticket),
        "magic": order.magic,
        "label": str(order.magic),
        "symbol": order.symbol,
        "type": _order_type_name(order.type),
        "openPrice": order.price_open,
        "volume": order.volume_initial,
        "stopLoss": _optional_price(order.sl),
        "takeProfit": _optional_price(order.tp),
        "openTime": order.time_setup,
    }


def _order_type_name(order_type: int) -> str:
    mapping = {
        mt5.ORDER_TYPE_BUY: "ORDER_TYPE_BUY",
        mt5.ORDER_TYPE_SELL: "ORDER_TYPE_SELL",
        mt5.ORDER_TYPE_BUY_LIMIT: "ORDER_TYPE_BUY_LIMIT",
        mt5.ORDER_TYPE_SELL_LIMIT: "ORDER_TYPE_SELL_LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "ORDER_TYPE_BUY_STOP",
        mt5.ORDER_TYPE_SELL_STOP: "ORDER_TYPE_SELL_STOP",
        mt5.ORDER_TYPE_BUY_STOP_LIMIT: "ORDER_TYPE_BUY_STOP_LIMIT",
        mt5.ORDER_TYPE_SELL_STOP_LIMIT: "ORDER_TYPE_SELL_STOP_LIMIT",
    }
    return mapping.get(order_type, "ORDER_TYPE_BUY_LIMIT")


def _optional_price(value: float) -> float | None:
    if value is None or value == 0.0:
        return None
    return float(value)
