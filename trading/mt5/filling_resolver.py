import MetaTrader5 as mt5

from trading.mt5.constants import (
    SYMBOL_FILLING_FOK,
    SYMBOL_FILLING_IOC,
    SYMBOL_FILLING_RETURN,
)
from trading.mt5.symbol_helper import ensure_symbol

_CHECK_OK = {0, mt5.TRADE_RETCODE_DONE}


def resolve_filling_mode(symbol: str, request: dict | None = None) -> int:
    """Symbol filling_mode bo'yicha ORDER_FILLING_* tanlaydi."""
    ensure_symbol(symbol)
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_RETURN

    candidates = _candidate_fillings(info.filling_mode)
    if request is not None:
        for mode in candidates:
            test_request = {**request, "type_filling": mode}
            check = mt5.order_check(test_request)
            if check is not None and check.retcode in _CHECK_OK:
                return mode

    return candidates[0] if candidates else mt5.ORDER_FILLING_RETURN


def _candidate_fillings(filling_mode: int) -> list[int]:
    pairs = [
        (SYMBOL_FILLING_RETURN, mt5.ORDER_FILLING_RETURN),
        (SYMBOL_FILLING_IOC, mt5.ORDER_FILLING_IOC),
        (SYMBOL_FILLING_FOK, mt5.ORDER_FILLING_FOK),
    ]
    selected = [order_fill for mask, order_fill in pairs if filling_mode & mask]
    if selected:
        return selected
    return [
        mt5.ORDER_FILLING_RETURN,
        mt5.ORDER_FILLING_IOC,
        mt5.ORDER_FILLING_FOK,
    ]
