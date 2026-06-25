import logging
from typing import Any

from models.existing_order import ExistingOrder
from trading.magic_matcher import matches_magic
from trading.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)

_BUY_TYPES = {"POSITION_TYPE_BUY", "ORDER_TYPE_BUY", "ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_BUY_STOP_LIMIT"}
_SELL_TYPES = {"POSITION_TYPE_SELL", "ORDER_TYPE_SELL", "ORDER_TYPE_SELL_LIMIT", "ORDER_TYPE_SELL_STOP", "ORDER_TYPE_SELL_STOP_LIMIT"}


class ExistingOrdersService:
    async def fetch(self, connection: Any, magic: int) -> list[ExistingOrder]:
        positions = await connection.get_positions()
        orders = await connection.get_orders()
        snapshot = TradingSnapshot(
            positions=list(positions or []),
            orders=list(orders or []),
        )
        return self.from_snapshot(snapshot, magic)

    def from_snapshot(
        self,
        snapshot: TradingSnapshot,
        magic: int,
    ) -> list[ExistingOrder]:
        orders: list[ExistingOrder] = []

        for raw in snapshot.positions:
            if not matches_magic(raw, magic):
                continue
            orders.append(self._from_position(raw))

        for raw in snapshot.orders:
            if not matches_magic(raw, magic):
                continue
            orders.append(self._from_pending(raw))

        return orders

    def count_for_magics(
        self,
        snapshot: TradingSnapshot,
        magics: list[int],
    ) -> int:
        total = 0
        for magic in magics:
            total += sum(
                1 for raw in snapshot.positions if matches_magic(raw, magic)
            )
            total += sum(
                1 for raw in snapshot.orders if matches_magic(raw, magic)
            )
        return total

    def _from_position(self, raw: dict) -> ExistingOrder:
        return ExistingOrder(
            order_number=str(raw.get("id", "")),
            open_time=_time_str(raw.get("time") or raw.get("openTime")),
            open_price=_float(raw.get("openPrice")) or 0.0,
            volume=_float(raw.get("volume")),
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
            volume=_float(raw.get("volume")),
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
