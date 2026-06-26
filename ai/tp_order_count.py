from ai.tp_levels_parser import parse_tp_levels
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.symbol_market_info import SymbolMarketInfo


def resolve_tp_levels(
    message_text: str | None,
    entries: list[AiOrderAction],
    reference_price: float | None = None,
) -> list[float]:
    """Xabar matnidagi TP lar ustuvor; yo'q bo'lsa entry orderlardan olinadi."""
    parsed = parse_tp_levels(message_text, reference_price)
    if parsed:
        return parsed

    seen: list[float] = []
    for item in entries:
        if item.tp is None or item.tp in seen:
            continue
        seen.append(item.tp)
    return seen


def resolve_target_entry_count(
    tp_levels: list[float],
    settings: Settings,
    existing_group_count: int,
    *,
    reserved_entries: int = 0,
) -> int:
    """Yangi entry orderlar soni: ustuvor — msg dagi TP lar soni."""
    channel_remaining = max(0, settings.max_order_count - existing_group_count)
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
