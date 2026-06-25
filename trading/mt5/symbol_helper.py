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


def normalize_volume(symbol: str, volume: float) -> float:
    ensure_symbol(symbol)
    info = mt5.symbol_info(symbol)
    if info is None:
        return volume

    step = info.volume_step or 0.01
    min_vol = info.volume_min or step
    max_vol = info.volume_max or volume
    clamped = max(min_vol, min(volume, max_vol))
    steps = max(1, round(clamped / step))
    return round(steps * step, 8)
