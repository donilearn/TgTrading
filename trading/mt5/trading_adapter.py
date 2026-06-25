import asyncio
import logging
from typing import Any

from trading.mt5.connection import MT5Connection
from trading.mt5 import order_builder as ob
from trading.mt5.symbol_helper import ensure_symbol, get_price_dict, get_spec_dict

logger = logging.getLogger(__name__)


class MT5TradingAdapter:
    """OrderRouter uchun MT5 adapter."""

    def __init__(self, connection: MT5Connection) -> None:
        self._connection = connection

    async def get_symbol_specification(self, symbol: str) -> dict:
        return await asyncio.to_thread(get_spec_dict, symbol)

    async def get_symbol_price(self, symbol: str) -> dict:
        return await asyncio.to_thread(get_price_dict, symbol)

    async def create_market_buy_order(self, **kwargs) -> dict:
        return await self._send_market(is_buy=True, **kwargs)

    async def create_market_sell_order(self, **kwargs) -> dict:
        return await self._send_market(is_buy=False, **kwargs)

    async def create_limit_buy_order(self, **kwargs) -> dict:
        return await self._send_pending(is_buy=True, kind="limit", **kwargs)

    async def create_limit_sell_order(self, **kwargs) -> dict:
        return await self._send_pending(is_buy=False, kind="limit", **kwargs)

    async def create_stop_buy_order(self, **kwargs) -> dict:
        return await self._send_pending(is_buy=True, kind="stop", **kwargs)

    async def create_stop_sell_order(self, **kwargs) -> dict:
        return await self._send_pending(is_buy=False, kind="stop", **kwargs)

    async def create_stop_limit_buy_order(self, **kwargs) -> dict:
        return await self._send_pending(is_buy=True, kind="stop_limit", **kwargs)

    async def create_stop_limit_sell_order(self, **kwargs) -> dict:
        return await self._send_pending(is_buy=False, kind="stop_limit", **kwargs)

    async def modify_position(self, **kwargs) -> dict:
        request = await asyncio.to_thread(
            ob.build_modify_position,
            str(kwargs["position_id"]),
            kwargs.get("stop_loss"),
            kwargs.get("take_profit"),
        )
        return await asyncio.to_thread(self._connection.send_request, request)

    async def modify_order(self, **kwargs) -> dict:
        request = await asyncio.to_thread(
            ob.build_modify_order,
            str(kwargs["order_id"]),
            kwargs.get("open_price"),
            kwargs.get("stop_loss"),
            kwargs.get("take_profit"),
        )
        return await asyncio.to_thread(self._connection.send_request, request)

    async def close_position(self, position_id: str, comment: str | None = None) -> dict:
        request = await asyncio.to_thread(
            ob.build_close_position, position_id, None, comment,
        )
        return await asyncio.to_thread(self._connection.send_request, request)

    async def close_position_partially(
        self, position_id: str, volume: float, comment: str | None = None,
    ) -> dict:
        request = await asyncio.to_thread(
            ob.build_close_position, position_id, volume, comment,
        )
        return await asyncio.to_thread(self._connection.send_request, request)

    async def cancel_order(self, order_id: str) -> dict:
        request = await asyncio.to_thread(ob.build_cancel_order, order_id)
        return await asyncio.to_thread(self._connection.send_request, request)

    async def close_positions_by_symbol(self, symbol: str) -> dict:
        await asyncio.to_thread(ensure_symbol, symbol)
        snapshot = await asyncio.to_thread(self._connection.fetch_snapshot)
        closed = 0
        for raw in snapshot.positions:
            if raw.get("symbol", "").upper() != symbol.upper():
                continue
            await self.close_position(str(raw["id"]))
            closed += 1
        return {"stringCode": "OK", "closed": closed}

    async def _send_market(
        self,
        is_buy: bool,
        symbol: str,
        volume: float,
        stop_loss: Any = None,
        take_profit: Any = None,
        options: dict | None = None,
        **_: Any,
    ) -> dict:
        request = await asyncio.to_thread(
            ob.build_market_order,
            symbol,
            volume,
            is_buy,
            _to_float(stop_loss),
            _to_float(take_profit),
            options,
        )
        return await asyncio.to_thread(self._connection.send_request, request)

    async def _send_pending(
        self,
        is_buy: bool,
        kind: str,
        symbol: str,
        volume: float,
        open_price: float | None = None,
        stop_loss: Any = None,
        take_profit: Any = None,
        stop_limit_price: float | None = None,
        options: dict | None = None,
        **_: Any,
    ) -> dict:
        if open_price is None:
            raise ValueError(f"{kind} order requires open_price")

        order_type = await asyncio.to_thread(ob.pending_type, is_buy, kind)
        request = await asyncio.to_thread(
            ob.build_pending_order,
            symbol,
            volume,
            is_buy,
            order_type,
            float(open_price),
            _to_float(stop_loss),
            _to_float(take_profit),
            stop_limit_price,
            options,
        )
        return await asyncio.to_thread(self._connection.send_request, request)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
