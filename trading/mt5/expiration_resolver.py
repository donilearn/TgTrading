import logging

import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

_SYMBOL_EXPIRATION_GTC = 1
_SYMBOL_EXPIRATION_DAY = 2
_SYMBOL_EXPIRATION_SPECIFIED = 4
_SYMBOL_EXPIRATION_SPECIFIED_DAY = 8

_MIN_EXPIRY_SEC = 120


def apply_mt5_pending_expiration(
    request: dict,
    symbol: str,
    minutes: int,
) -> None:
    """Pending orderga broker/symbol qoidalariga mos expiration qo'yadi."""
    if minutes <= 0:
        return

    info = mt5.symbol_info(symbol)
    if info is None:
        logger.warning("MT5 expiration skipped — unknown symbol %s", symbol)
        return

    server_ts = _server_timestamp(symbol)
    if server_ts is None:
        logger.warning("MT5 expiration skipped — no server time for %s", symbol)
        return

    mode = int(getattr(info, "expiration_mode", 0) or 0)
    expiry_sec = _resolve_expiry_seconds(symbol, minutes)
    target_ts = server_ts + expiry_sec

    if mode & _SYMBOL_EXPIRATION_SPECIFIED:
        request["type_time"] = mt5.ORDER_TIME_SPECIFIED
        request["expiration"] = target_ts
        return

    if mode & _SYMBOL_EXPIRATION_SPECIFIED_DAY:
        request["type_time"] = mt5.ORDER_TIME_SPECIFIED_DAY
        request["expiration"] = _end_of_server_day_ts(server_ts)
        logger.info(
            "Symbol %s: ORDER_TIME_SPECIFIED not allowed — using SPECIFIED_DAY",
            symbol,
        )
        return

    if mode & _SYMBOL_EXPIRATION_DAY:
        request["type_time"] = mt5.ORDER_TIME_DAY
        request.pop("expiration", None)
        logger.info(
            "Symbol %s: using ORDER_TIME_DAY (requested %d min)",
            symbol,
            minutes,
        )
        return

    request["type_time"] = mt5.ORDER_TIME_GTC
    request.pop("expiration", None)
    logger.info(
        "Symbol %s expiration_mode=%s — GTC only (requested %d min ignored)",
        symbol,
        mode,
        minutes,
    )


def _resolve_expiry_seconds(symbol: str, minutes: int) -> int:
    requested_sec = minutes * 60
    if requested_sec >= _MIN_EXPIRY_SEC:
        return requested_sec

    logger.warning(
        "Symbol %s: requested expiration %d min (%ds) below broker minimum %ds — using %ds",
        symbol,
        minutes,
        requested_sec,
        _MIN_EXPIRY_SEC,
        _MIN_EXPIRY_SEC,
    )
    return _MIN_EXPIRY_SEC


def _server_timestamp(symbol: str) -> int | None:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    return int(tick.time)


def _end_of_server_day_ts(server_ts: int) -> int:
    seconds_in_day = 24 * 60 * 60
    day_start = server_ts - (server_ts % seconds_in_day)
    return day_start + seconds_in_day - 1