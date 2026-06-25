import MetaTrader5 as mt5


def ensure_symbol(symbol: str) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"Unknown MT5 symbol: {symbol}")
    if not info.visible:
        if not mt5.symbol_select(symbol, True):
            raise ValueError(f"Failed to select symbol: {symbol}")


def get_spec_dict(symbol: str) -> dict:
    ensure_symbol(symbol)
    info = mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"Symbol spec not found: {symbol}")

    tick_size = info.trade_tick_size or info.point
    return {
        "symbolName": symbol,
        "digits": info.digits,
        "tickSize": tick_size,
        "volumeStep": info.volume_step,
        "minVolume": info.volume_min,
    }


def get_price_dict(symbol: str) -> dict:
    ensure_symbol(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"bid": None, "ask": None}
    return {"bid": tick.bid, "ask": tick.ask}


def resolve_filling_mode(symbol: str) -> int:
    ensure_symbol(symbol)
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_RETURN

    filling = info.filling_mode
    if filling & mt5.SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    if filling & mt5.SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN
