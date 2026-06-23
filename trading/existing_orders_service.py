import logging
from typing import Any

from models.existing_order import ExistingOrder
from trading.magic_matcher import matches_magic

logger = logging.getLogger(__name__)

_BUY_TYPES = {"POSITION_TYPE_BUY", "ORDER_TYPE_BUY", "ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_BUY_STOP_LIMIT"}
_SELL_TYPES = {"POSITION_TYPE_SELL", "ORDER_TYPE_SELL", "ORDER_TYPE_SELL_LIMIT", "ORDER_TYPE_SELL_STOP", "ORDER_TYPE_SELL_STOP_LIMIT"}


class ExistingOrdersService:
    async def fetch(self, connection: Any, magic: int) -> list[ExistingOrder]:
        orders: list[ExistingOrder] = []

        for raw in await connection.get_positions():
            if not matches_magic(raw, magic):
                continue
            orders.append(self._from_position(raw))

        for raw in await connection.get_orders():
            if not matches_magic(raw, magic):
                continue
            orders.append(self._from_pending(raw))

        return orders

    async def fetch_global_count(self, connection, magics: list[int]) -> int:
        total = 0
        for magic in magics:
            total += len(await self.fetch(connection, magic))
        return total

    def _from_position(self, raw: dict) -> ExistingOrder:
        return ExistingOrder(
            order_number=str(raw.get("id", "")),
            open_time=_time_str(raw.get("time") or raw.get("openTime")),
            open_price=_float(raw.get("openPrice")) or 0.0,
            stop_loss=_float(raw.get("stopLoss")),
            take_profit=_float(raw.get("takeProfit")),
            side=_side(raw.get("type", "")),
            order_type="market",
            symbol=str(raw.get("symbol", "")),
            is_position=True,
        )

    def _from_pending(self, raw: dict) -> ExistingOrder:
        return ExistingOrder(
            order_number=str(raw.get("id", "")),
            open_time=_time_str(raw.get("time") or raw.get("openTime")),
            open_price=_float(raw.get("openPrice")) or 0.0,
            stop_loss=_float(raw.get("stopLoss")),
            take_profit=_float(raw.get("takeProfit")),
            side=_side(raw.get("type", "")),
            order_type=_pending_type(raw.get("type", "")),
            symbol=str(raw.get("symbol", "")),
            is_position=False,
        )


def _side(raw_type: str) -> str:
    upper = str(raw_type).upper()
    if upper in _BUY_TYPES or "BUY" in upper:
        return "buy"
    if upper in _SELL_TYPES or "SELL" in upper:
        return "sell"
    return "none"


def _pending_type(raw_type: str) -> str:
    upper = str(raw_type).upper()
    if "LIMIT" in upper:
        return "limit"
    if "STOP" in upper:
        return "stop"
    return "limit"


def _time_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
