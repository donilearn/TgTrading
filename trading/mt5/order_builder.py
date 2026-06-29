from datetime import datetime
from typing import Any

import MetaTrader5 as mt5

from trading.mt5.filling_resolver import resolve_filling_mode
from trading.mt5.symbol_helper import ensure_symbol, get_price_dict, normalize_volume
from trading.order_comment import sanitize_mt5_comment


def build_market_order(
    symbol: str,
    volume: float,
    is_buy: bool,
    stop_loss: float | None,
    take_profit: float | None,
    options: dict | None,
) -> dict:
    volume = normalize_volume(symbol, volume)
    ensure_symbol(symbol)
    tick = get_price_dict(symbol)
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
    price = tick["ask"] if is_buy else tick["bid"]
    if price is None:
        raise ValueError(f"No market price for {symbol}")

    request = _base_request(symbol, volume, options)
    request.update({
        "action": mt5.TRADE_ACTION_DEAL,
        "type": order_type,
        "price": price,
        "type_time": mt5.ORDER_TIME_GTC,
    })
    _apply_stops(request, stop_loss, take_profit)
    request["type_filling"] = resolve_filling_mode(symbol, request)
    return request


def build_pending_order(
    symbol: str,
    volume: float,
    is_buy: bool,
    order_type: int,
    price: float,
    stop_loss: float | None,
    take_profit: float | None,
    stop_limit_price: float | None,
    options: dict | None,
) -> dict:
    volume = normalize_volume(symbol, volume)
    ensure_symbol(symbol)
    request = _base_request(symbol, volume, options)
    request.update({
        "action": mt5.TRADE_ACTION_PENDING,
        "type": order_type,
        "price": price,
        "type_time": mt5.ORDER_TIME_GTC,
    })

    if order_type in (mt5.ORDER_TYPE_BUY_STOP_LIMIT, mt5.ORDER_TYPE_SELL_STOP_LIMIT):
        if stop_limit_price is None:
            raise ValueError("stop_limit order requires stop_limit_price")
        request["stoplimit"] = stop_limit_price

    _apply_stops(request, stop_loss, take_profit)
    _apply_expiration(request, options)
    return request


def build_modify_position(
    position_id: str,
    stop_loss: float | None,
    take_profit: float | None,
) -> dict:
    positions = mt5.positions_get(ticket=int(position_id))
    if not positions:
        raise ValueError(f"Position {position_id} not found")

    pos = positions[0]
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": int(position_id),
        "symbol": pos.symbol,
        "sl": stop_loss if stop_loss is not None else pos.sl,
        "tp": take_profit if take_profit is not None else pos.tp,
    }
    return request


def build_modify_order(
    order_id: str,
    open_price: float | None,
    stop_loss: float | None,
    take_profit: float | None,
) -> dict:
    orders = mt5.orders_get(ticket=int(order_id))
    if not orders:
        raise ValueError(f"Order {order_id} not found")

    order = orders[0]
    request = {
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": int(order_id),
        "symbol": order.symbol,
        "type": order.type,
        "price": open_price if open_price is not None else order.price_open,
        "sl": stop_loss if stop_loss is not None else order.sl,
        "tp": take_profit if take_profit is not None else order.tp,
        "type_time": order.type_time,
    }
    if order.type_time == mt5.ORDER_TIME_SPECIFIED:
        request["expiration"] = order.time_expiration
    return request


def build_close_position(
    position_id: str,
    volume: float | None = None,
    comment: str | None = None,
) -> dict:
    positions = mt5.positions_get(ticket=int(position_id))
    if not positions:
        raise ValueError(f"Position {position_id} not found")

    pos = positions[0]
    if volume is not None:
        close_volume = volume
    else:
        close_volume = pos.volume
    close_volume = normalize_volume(pos.symbol, close_volume)
    is_buy = pos.type == mt5.POSITION_TYPE_BUY
    order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY

    tick = get_price_dict(pos.symbol)
    price = tick["bid"] if is_buy else tick["ask"]
    if price is None:
        raise ValueError(f"No price to close {pos.symbol}")

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": close_volume,
        "type": order_type,
        "position": int(position_id),
        "price": price,
        "deviation": 20,
        "magic": pos.magic,
        "comment": sanitize_mt5_comment(comment or "close"),
        "type_time": mt5.ORDER_TIME_GTC,
    }
    request["type_filling"] = resolve_filling_mode(pos.symbol, request)
    return request


def build_cancel_order(order_id: str) -> dict:
    orders = mt5.orders_get(ticket=int(order_id))
    if not orders:
        raise ValueError(f"Order {order_id} not found")

    order = orders[0]
    return {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": int(order_id),
        "symbol": order.symbol,
    }


def pending_type(is_buy: bool, kind: str) -> int:
    mapping = {
        ("buy", "limit"): mt5.ORDER_TYPE_BUY_LIMIT,
        ("sell", "limit"): mt5.ORDER_TYPE_SELL_LIMIT,
        ("buy", "stop"): mt5.ORDER_TYPE_BUY_STOP,
        ("sell", "stop"): mt5.ORDER_TYPE_SELL_STOP,
        ("buy", "stop_limit"): mt5.ORDER_TYPE_BUY_STOP_LIMIT,
        ("sell", "stop_limit"): mt5.ORDER_TYPE_SELL_STOP_LIMIT,
    }
    side = "buy" if is_buy else "sell"
    key = (side, kind)
    if key not in mapping:
        raise ValueError(f"Unsupported pending type: {kind} {side}")
    return mapping[key]


def _base_request(symbol: str, volume: float, options: dict | None) -> dict:
    opts = options or {}
    request = {
        "symbol": symbol,
        "volume": normalize_volume(symbol, volume),
        "deviation": 20,
        "comment": sanitize_mt5_comment(str(opts.get("comment", "TG"))),
        "type_time": mt5.ORDER_TIME_GTC,
    }
    magic = opts.get("magic")
    if magic is not None:
        request["magic"] = int(magic)
    return request


def _apply_stops(request: dict, stop_loss: float | None, take_profit: float | None) -> None:
    if stop_loss is not None:
        request["sl"] = float(stop_loss)
    if take_profit is not None:
        request["tp"] = float(take_profit)


def _apply_expiration(request: dict, options: dict | None) -> None:
    if not options:
        return

    expiration = options.get("expiration")
    if not expiration:
        return

    exp_time = expiration.get("time")
    if not isinstance(exp_time, datetime):
        return

    request["type_time"] = mt5.ORDER_TIME_SPECIFIED
    request["expiration"] = int(exp_time.timestamp())
