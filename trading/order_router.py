import logging
from typing import Any

from models.order_type import OrderType
from models.signal import SignalAnalysis, TradeAction
from trading.stop_options_builder import build_stop_options

logger = logging.getLogger(__name__)


class OrderRouter:
    """Routes signal to the correct MetaAPI order method."""

    async def place_order(
        self,
        connection: Any,
        signal: SignalAnalysis,
        volume: float,
        entry_price: float | None,
        stop_loss: float | None,
        take_profit: float | None,
        sl_pips: float | None,
        tp_pips: float | None,
        options: dict,
        order_type: OrderType | None = None,
    ) -> dict:
        symbol = signal.symbol
        sl = build_stop_options(stop_loss, sl_pips)
        tp = build_stop_options(take_profit, tp_pips)
        action = signal.action
        effective_type = order_type or signal.order_type

        if effective_type == OrderType.MARKET:
            return await self._market_order(
                connection, symbol, action, volume, sl, tp, options,
            )

        if entry_price is None:
            raise ValueError(f"{effective_type.value} order requires entry price")

        if effective_type == OrderType.LIMIT:
            return await self._limit_order(
                connection, symbol, action, volume, entry_price, sl, tp, options,
            )

        if effective_type == OrderType.STOP:
            return await self._stop_order(
                connection, symbol, action, volume, entry_price, sl, tp, options,
            )

        if effective_type == OrderType.STOP_LIMIT:
            if signal.stop_limit_price is None:
                raise ValueError("stop_limit order requires stop_limit_price")
            return await self._stop_limit_order(
                connection, symbol, action, volume, entry_price,
                signal.stop_limit_price, sl, tp, options,
            )

        raise ValueError(f"Unsupported order type: {effective_type}")

    async def _market_order(
        self, connection, symbol, action, volume, sl, tp, options,
    ) -> dict:
        kwargs = {"symbol": symbol, "volume": volume, "options": options}
        _apply_stops(kwargs, sl, tp)

        if action == TradeAction.BUY:
            return await connection.create_market_buy_order(**kwargs)
        return await connection.create_market_sell_order(**kwargs)

    async def _limit_order(
        self, connection, symbol, action, volume, price, sl, tp, options,
    ) -> dict:
        kwargs = {
            "symbol": symbol,
            "volume": volume,
            "open_price": price,
            "options": options,
        }
        _apply_stops(kwargs, sl, tp)

        if action == TradeAction.BUY:
            return await connection.create_limit_buy_order(**kwargs)
        return await connection.create_limit_sell_order(**kwargs)

    async def _stop_order(
        self, connection, symbol, action, volume, price, sl, tp, options,
    ) -> dict:
        kwargs = {
            "symbol": symbol,
            "volume": volume,
            "open_price": price,
            "options": options,
        }
        _apply_stops(kwargs, sl, tp)

        if action == TradeAction.BUY:
            return await connection.create_stop_buy_order(**kwargs)
        return await connection.create_stop_sell_order(**kwargs)

    async def _stop_limit_order(
        self, connection, symbol, action, volume, price, stop_limit, sl, tp, options,
    ) -> dict:
        kwargs = {
            "symbol": symbol,
            "volume": volume,
            "open_price": price,
            "stop_limit_price": stop_limit,
            "options": options,
        }
        _apply_stops(kwargs, sl, tp)

        if action == TradeAction.BUY:
            return await connection.create_stop_limit_buy_order(**kwargs)
        return await connection.create_stop_limit_sell_order(**kwargs)

    async def close_symbol(self, connection: Any, symbol: str) -> dict:
        return await connection.close_positions_by_symbol(symbol=symbol)


def _apply_stops(kwargs: dict, sl, tp) -> None:
    if sl is not None:
        kwargs["stop_loss"] = sl
    if tp is not None:
        kwargs["take_profit"] = tp
