import logging
from datetime import datetime
from typing import Any

from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAmendOrderReq,
    ProtoOAAmendPositionSLTPReq,
    ProtoOACancelOrderReq,
    ProtoOAClosePositionReq,
    ProtoOANewOrderReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
    ProtoOAOrderType,
    ProtoOATimeInForce,
    ProtoOATradeSide,
)
from ctrader_open_api.protobuf import Protobuf

from trading.ctrader.converters import lots_to_volume
from trading.ctrader.session import CTraderSession

logger = logging.getLogger(__name__)


class CTraderTradingAdapter:
    """MetaAPI connection interfeysi o'rniga — OrderRouter uchun."""

    def __init__(self, session: CTraderSession) -> None:
        self._session = session

    async def get_symbol_specification(self, symbol: str) -> dict:
        spec = self._session.registry.get_spec(symbol)
        if spec is None:
            symbol_id = self._session.registry.resolve_id(symbol)
            if symbol_id is None:
                raise ValueError(f"Unknown symbol: {symbol}")
            from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolByIdReq

            req = ProtoOASymbolByIdReq()
            req.ctidTraderAccountId = self._session._account_id
            req.symbolId.append(symbol_id)
            res = await self._session.request(req)
            payload = Protobuf.extract(res)
            if not payload.symbol:
                raise ValueError(f"Symbol spec not found: {symbol}")
            from trading.ctrader.session import _symbol_spec_dict

            spec = _symbol_spec_dict(payload.symbol[0])
            spec["symbolName"] = self._session.registry.resolve_name(symbol_id)
            self._session.registry.register_spec(symbol_id, spec)
        return spec

    async def get_symbol_price(self, symbol: str) -> dict:
        symbol_id = self._require_symbol_id(symbol)
        quote = self._session.spots.get(symbol_id)
        if quote is None:
            await self._session.subscribe_symbols([symbol])
            quote = self._session.spots.get(symbol_id)
        return {
            "bid": quote.bid if quote else None,
            "ask": quote.ask if quote else None,
        }

    async def create_market_buy_order(self, **kwargs) -> dict:
        return await self._place_order(ProtoOATradeSide.BUY, ProtoOAOrderType.MARKET, **kwargs)

    async def create_market_sell_order(self, **kwargs) -> dict:
        return await self._place_order(ProtoOATradeSide.SELL, ProtoOAOrderType.MARKET, **kwargs)

    async def create_limit_buy_order(self, **kwargs) -> dict:
        return await self._place_order(ProtoOATradeSide.BUY, ProtoOAOrderType.LIMIT, **kwargs)

    async def create_limit_sell_order(self, **kwargs) -> dict:
        return await self._place_order(ProtoOATradeSide.SELL, ProtoOAOrderType.LIMIT, **kwargs)

    async def create_stop_buy_order(self, **kwargs) -> dict:
        return await self._place_order(ProtoOATradeSide.BUY, ProtoOAOrderType.STOP, **kwargs)

    async def create_stop_sell_order(self, **kwargs) -> dict:
        return await self._place_order(ProtoOATradeSide.SELL, ProtoOAOrderType.STOP, **kwargs)

    async def create_stop_limit_buy_order(self, **kwargs) -> dict:
        return await self._place_order(
            ProtoOATradeSide.BUY,
            ProtoOAOrderType.STOP_LIMIT,
            **kwargs,
        )

    async def create_stop_limit_sell_order(self, **kwargs) -> dict:
        return await self._place_order(
            ProtoOATradeSide.SELL,
            ProtoOAOrderType.STOP_LIMIT,
            **kwargs,
        )

    async def modify_position(self, **kwargs) -> dict:
        req = ProtoOAAmendPositionSLTPReq()
        req.ctidTraderAccountId = self._session._account_id
        req.positionId = int(kwargs["position_id"])
        if kwargs.get("stop_loss") is not None:
            req.stopLoss = float(kwargs["stop_loss"])
        if kwargs.get("take_profit") is not None:
            req.takeProfit = float(kwargs["take_profit"])
        await self._session.request(req)
        return {"stringCode": "OK"}

    async def modify_order(self, **kwargs) -> dict:
        req = ProtoOAAmendOrderReq()
        req.ctidTraderAccountId = self._session._account_id
        req.orderId = int(kwargs["order_id"])
        if kwargs.get("open_price") is not None:
            req.limitPrice = float(kwargs["open_price"])
        if kwargs.get("stop_loss") is not None:
            req.stopLoss = float(kwargs["stop_loss"])
        if kwargs.get("take_profit") is not None:
            req.takeProfit = float(kwargs["take_profit"])
        await self._session.request(req)
        return {"stringCode": "OK"}

    async def close_position(self, position_id: str) -> dict:
        snapshot = await self._session.fetch_snapshot()
        volume = _find_position_volume(snapshot.positions, position_id)
        req = ProtoOAClosePositionReq()
        req.ctidTraderAccountId = self._session._account_id
        req.positionId = int(position_id)
        req.volume = lots_to_volume(volume)
        await self._session.request(req)
        return {"stringCode": "OK"}

    async def close_position_partially(self, position_id: str, volume: float) -> dict:
        req = ProtoOAClosePositionReq()
        req.ctidTraderAccountId = self._session._account_id
        req.positionId = int(position_id)
        req.volume = lots_to_volume(volume)
        await self._session.request(req)
        return {"stringCode": "OK"}

    async def cancel_order(self, order_id: str) -> dict:
        req = ProtoOACancelOrderReq()
        req.ctidTraderAccountId = self._session._account_id
        req.orderId = int(order_id)
        await self._session.request(req)
        return {"stringCode": "OK"}

    async def close_positions_by_symbol(self, symbol: str) -> dict:
        snapshot = await self._session.fetch_snapshot()
        closed = 0
        for raw in snapshot.positions:
            if raw.get("symbol", "").upper() != symbol.upper():
                continue
            await self.close_position(str(raw["id"]))
            closed += 1
        return {"stringCode": "OK", "closed": closed}

    async def _place_order(
        self,
        trade_side: int,
        order_type: int,
        symbol: str,
        volume: float,
        open_price: float | None = None,
        stop_loss: Any = None,
        take_profit: Any = None,
        stop_limit_price: float | None = None,
        options: dict | None = None,
    ) -> dict:
        symbol_id = self._require_symbol_id(symbol)
        opts = options or {}

        req = ProtoOANewOrderReq()
        req.ctidTraderAccountId = self._session._account_id
        req.symbolId = symbol_id
        req.orderType = order_type
        req.tradeSide = trade_side
        req.volume = lots_to_volume(volume)

        if open_price is not None and order_type in (
            ProtoOAOrderType.LIMIT,
            ProtoOAOrderType.STOP,
            ProtoOAOrderType.STOP_LIMIT,
        ):
            if order_type == ProtoOAOrderType.LIMIT:
                req.limitPrice = float(open_price)
            else:
                req.stopPrice = float(open_price)

        if order_type == ProtoOAOrderType.STOP_LIMIT and stop_limit_price is not None:
            req.limitPrice = float(stop_limit_price)

        if stop_loss is not None:
            req.stopLoss = float(stop_loss)
        if take_profit is not None:
            req.takeProfit = float(take_profit)

        magic = opts.get("magic")
        if magic is not None:
            req.label = str(magic)
        if opts.get("comment"):
            req.comment = str(opts["comment"])[:512]
        if opts.get("clientId"):
            req.clientOrderId = str(opts["clientId"])[:50]

        expiration = opts.get("expiration")
        if expiration and order_type != ProtoOAOrderType.MARKET:
            exp_time = expiration.get("time")
            if isinstance(exp_time, datetime):
                req.expirationTimestamp = int(exp_time.timestamp() * 1000)
                req.timeInForce = ProtoOATimeInForce.GOOD_TILL_DATE

        await self._session.request(req)
        return {"stringCode": "OK"}

    def _require_symbol_id(self, symbol: str) -> int:
        symbol_id = self._session.registry.resolve_id(symbol)
        if symbol_id is None:
            raise ValueError(f"Unknown cTrader symbol: {symbol}")
        return symbol_id


def _find_position_volume(positions: list[dict], position_id: str) -> float:
    for item in positions:
        if str(item.get("id")) == str(position_id):
            vol = item.get("volume")
            return float(vol) if vol is not None else 0.01
    raise ValueError(f"Position {position_id} not found for close")
