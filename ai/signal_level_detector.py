import re

from ai.sl_level_parser import parse_sl_level
from ai.tp_order_count import message_tp_level_count
from ai.zone_bounds_parser import parse_zone_bounds
from models.ai_trade_response import AiTradeResponse

_DIRECTION_HINT = re.compile(
    r"\b(buy|sell|long|short|gold\s+sell|gold\s+buy)\b",
    re.IGNORECASE,
)


def message_text_has_trade_levels(
    message_text: str | None,
    response: AiTradeResponse,
    *,
    reference_price: float | None = None,
) -> bool:
    """Faqat xabar matni + zone maydonlari (AI orderlarini hisobga olmaydi)."""
    if parse_sl_level(message_text, reference_price) is not None:
        return True
    tp_count = message_tp_level_count(message_text, reference_price)
    if tp_count is not None and tp_count >= 1:
        return True
    if parse_zone_bounds(message_text, reference_price) is not None:
        return True
    if response.zone_low is not None and response.zone_high is not None:
        if response.zone_low != response.zone_high:
            return True
    return False


def message_has_trade_levels(
    message_text: str | None,
    response: AiTradeResponse,
    *,
    reference_price: float | None = None,
) -> bool:
    """Xabarda entry zone, SL yoki TP bor-yo'qligi (Case #2 / Case #1 2-qadam)."""
    if message_text_has_trade_levels(message_text, response, reference_price=reference_price):
        return True
    for item in response.orders:
        if item.action_type.lower() != "entry":
            continue
        if item.sl is not None or item.tp is not None:
            return True
        if item.price is not None and item.order_type.lower() in ("limit", "stop"):
            return True
    return False


def is_direction_only_signal(
    message_text: str | None,
    response: AiTradeResponse,
    *,
    reference_price: float | None = None,
) -> bool:
    """Faqat yo'nalish (Case #1 1-qadam): sell/buy, lekin SL/TP/zone yo'q."""
    if not response.is_signal or not response.side or response.side.lower() == "none":
        return False
    if message_text_has_trade_levels(message_text, response, reference_price=reference_price):
        return False
    text = message_text or ""
    if _DIRECTION_HINT.search(text):
        return True
    return bool(response.orders) and all(
        o.action_type.lower() == "entry" and o.order_type.lower() == "market"
        for o in response.orders
    )
