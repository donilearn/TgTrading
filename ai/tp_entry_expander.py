import logging

from ai.tp_order_count import (
    reference_price_from_market,
    resolve_target_entry_count,
    resolve_tp_levels,
)
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.symbol_market_info import SymbolMarketInfo
from trading.volume_normalizer import split_volume_for_zone
from trading.zone_price_distribution import evenly_spaced_prices

logger = logging.getLogger(__name__)


def expand_tp_entry_orders(
    response: AiTradeResponse,
    settings: Settings,
    existing_group_count: int,
    message_text: str | None = None,
    market: list[SymbolMarketInfo] | None = None,
) -> AiTradeResponse:
    """Har bir TP level uchun alohida entry order (soni msg TP lariga bog'liq)."""
    if not response.is_signal:
        return response

    entries = [item for item in response.orders if item.action_type.lower() == "entry"]
    management = [
        item for item in response.orders if item.action_type.lower() != "entry"
    ]
    if not entries:
        return response

    reference_price = reference_price_from_market(response.symbol, market)
    tp_levels = resolve_tp_levels(message_text, entries, reference_price)
    if len(tp_levels) <= 1:
        return response

    target_count = resolve_target_entry_count(
        tp_levels,
        settings,
        existing_group_count,
    )
    if target_count <= 0:
        return response

    if len(entries) >= target_count and _entries_match_tps(entries, tp_levels, target_count):
        return response

    if target_count <= len(entries):
        return _assign_missing_tps(response, entries, management, tp_levels, target_count)

    template = entries[0]
    total_volume = sum(
        item.volume or settings.default_volume for item in entries
    )
    volumes, _ = split_volume_for_zone(
        total_volume,
        target_count,
        settings.min_volume,
        settings.max_volume,
    )
    prices = _entry_prices(response, template, target_count)

    expanded = [
        AiOrderAction(
            count_order=1,
            action_type="entry",
            price=prices[index],
            sl=template.sl,
            tp=tp_levels[index],
            order_type=template.order_type,
            volume=volumes[index],
            expiration_minutes=template.expiration_minutes,
        )
        for index in range(target_count)
    ]

    logger.info(
        "TP entry expand: %d TP → %d entry order(s) (was %d)",
        len(tp_levels),
        target_count,
        len(entries),
    )
    return response.model_copy(update={"orders": management + expanded})


def _entries_match_tps(
    entries: list[AiOrderAction],
    tp_levels: list[float],
    target_count: int,
) -> bool:
    for index in range(target_count):
        if entries[index].tp != tp_levels[index]:
            return False
    return True


def _assign_missing_tps(
    response: AiTradeResponse,
    entries: list[AiOrderAction],
    management: list[AiOrderAction],
    tp_levels: list[float],
    target_count: int,
) -> AiTradeResponse:
    updated: list[AiOrderAction] = []
    changed = False
    for index, item in enumerate(entries[:target_count]):
        expected_tp = tp_levels[index]
        if item.tp == expected_tp:
            updated.append(item)
            continue
        changed = True
        updated.append(item.model_copy(update={"tp": expected_tp}))

    if not changed:
        return response

    rest = entries[target_count:]
    logger.info("TP assign: %d entry order(s) ga TP yangilandi", len(updated))
    return response.model_copy(update={"orders": management + updated + rest})


def _entry_prices(
    response: AiTradeResponse,
    template: AiOrderAction,
    count: int,
) -> list[float | None]:
    if response.zone_low is not None and response.zone_high is not None:
        low = min(response.zone_low, response.zone_high)
        high = max(response.zone_low, response.zone_high)
        if low != high:
            return evenly_spaced_prices(low, high, count)

    explicit = [
        item.price
        for item in response.orders
        if item.action_type.lower() == "entry" and item.price is not None
    ]
    if len(explicit) >= count:
        return explicit[:count]

    return [template.price] * count
