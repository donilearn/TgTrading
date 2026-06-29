from ai.tp_levels_parser import parse_tp_levels
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.symbol_market_info import SymbolMarketInfo


def message_tp_levels(
    message_text: str | None,
    reference_price: float | None = None,
) -> list[float]:
    """Faqat xabar matnidagi TP lar (parser)."""
    if not message_text:
        return []
    return parse_tp_levels(message_text, reference_price)


def resolve_tp_levels(
    message_text: str | None,
    entries: list[AiOrderAction],
    reference_price: float | None = None,
) -> tuple[list[float], bool]:
    """TP lar va xabar matnidan olinganligi (from_message)."""
    parsed = message_tp_levels(message_text, reference_price)
    if parsed:
        return parsed, True

    seen: list[float] = []
    for item in entries:
        if item.tp is None or item.tp in seen:
            continue
        seen.append(item.tp)
    return seen, False


def resolve_target_entry_count(
    tp_levels: list[float],
    settings: Settings,
    existing_group_count: int,
    *,
    tp_from_message: bool = False,
    reserved_entries: int = 0,
) -> int:
    """Yangi entry orderlar soni. Xabar TP lari MAX_ORDER_PER_GROUP dan ustun."""
    channel_remaining = max(0, settings.max_order_count - existing_group_count)

    if tp_levels and tp_from_message:
        return min(len(tp_levels), channel_remaining)

    msg_slots = max(0, settings.effective_max_per_message - reserved_entries)
    hard_cap = min(msg_slots, channel_remaining)

    if tp_levels:
        return min(len(tp_levels), hard_cap)

    return hard_cap


def reference_price_from_market(
    symbol: str | None,
    market: list[SymbolMarketInfo] | None,
) -> float | None:
    if not symbol or not market:
        return None

    for item in market:
        if item.symbol != symbol:
            continue
        if item.bid is not None and item.ask is not None:
            return (item.bid + item.ask) / 2
        return item.bid or item.ask
    return None
