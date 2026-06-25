from typing import Any

from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
    ProtoOAOrder,
    ProtoOAPosition,
    ProtoOATradeSide,
)

from trading.ctrader.converters import volume_to_lots
from trading.ctrader.symbol_registry import SymbolRegistry
from trading.trading_snapshot import TradingSnapshot


class SnapshotMapper:
    def __init__(self, registry: SymbolRegistry) -> None:
        self._registry = registry

    def from_reconcile(
        self,
        positions: list[ProtoOAPosition],
        orders: list[ProtoOAOrder],
    ) -> TradingSnapshot:
        return TradingSnapshot(
            positions=[self._map_position(item) for item in positions],
            orders=[self._map_order(item) for item in orders],
        )

    def _map_position(self, position: ProtoOAPosition) -> dict[str, Any]:
        trade = position.tradeData
        symbol_id = trade.symbolId
        label = trade.label or ""
        side = _trade_side(trade.tradeSide)
        return {
            "id": str(position.positionId),
            "magic": label,
            "label": label,
            "symbol": self._registry.resolve_name(symbol_id),
            "type": f"POSITION_TYPE_{side.upper()}",
            "openPrice": position.price,
            "volume": volume_to_lots(trade.volume),
            "stopLoss": position.stopLoss or None,
            "takeProfit": position.takeProfit or None,
            "openTime": trade.openTimestamp,
        }

    def _map_order(self, order: ProtoOAOrder) -> dict[str, Any]:
        trade = order.tradeData
        symbol_id = trade.symbolId
        label = trade.label or ""
        side = _trade_side(trade.tradeSide)
        order_type = _order_type_name(order.orderType)
        price = order.limitPrice or order.stopPrice or order.executionPrice or 0.0
        return {
            "id": str(order.orderId),
            "magic": label,
            "label": label,
            "symbol": self._registry.resolve_name(symbol_id),
            "type": f"ORDER_TYPE_{side.upper()}_{order_type.upper()}",
            "openPrice": price,
            "volume": volume_to_lots(trade.volume),
            "stopLoss": order.stopLoss or None,
            "takeProfit": order.takeProfit or None,
            "openTime": trade.openTimestamp,
        }


def _trade_side(value: int) -> str:
    if value == ProtoOATradeSide.BUY:
        return "buy"
    if value == ProtoOATradeSide.SELL:
        return "sell"
    return "none"


def _order_type_name(order_type: int) -> str:
    mapping = {1: "market", 2: "limit", 3: "stop", 4: "market_range", 5: "stop_limit"}
    return mapping.get(order_type, "limit")
