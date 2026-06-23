import logging

from ai.tp_levels_parser import parse_tp_levels
from ai.zone_bounds_parser import parse_zone_bounds
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.symbol_market_info import SymbolMarketInfo
from trading.volume_normalizer import split_volume_for_zone
from trading.zone_price_distribution import evenly_spaced_prices

logger = logging.getLogger(__name__)

_GRID_ORDER_TYPES = frozenset({"limit", "stop"})


def expand_zone_grid_orders(
    response: AiTradeResponse,
    settings: Settings,
    existing_group_count: int,
    global_order_count: int | None = None,
    message_text: str | None = None,
    market: list[SymbolMarketInfo] | None = None,
) -> AiTradeResponse:
    """Aggressive mode: zone signalini to'liq grid orderlarga kengaytiradi."""
    if not settings.aggressive_mode or not response.is_signal:
        return response

    entries = [item for item in response.orders if item.action_type.lower() == "entry"]
    management = [
        item for item in response.orders if item.action_type.lower() != "entry"
    ]

    market_entries = [
        item for item in entries if item.order_type.lower() == "market"
    ]
    grid_entries = [
        item for item in entries
        if item.order_type.lower() in _GRID_ORDER_TYPES
    ]

    reference_price = _reference_price(response.symbol, market)
    zone = _resolve_zone_bounds(response, grid_entries, message_text, reference_price)
    if zone is None:
        return response

    zone_low, zone_high = zone
    channel_remaining = max(0, settings.max_order_count - existing_group_count)

    msg_slots = max(0, settings.max_order_per_group - len(market_entries))
    grid_count = min(msg_slots, channel_remaining)

    if grid_count <= 0:
        return response

    if len(grid_entries) >= grid_count:
        return response

    grid_prices = evenly_spaced_prices(zone_low, zone_high, grid_count)
    template = grid_entries[0] if grid_entries else _default_template(entries, settings)
    tp_levels = _resolve_tp_levels(message_text, entries, reference_price)
    total_volume = template.volume or settings.default_volume
    volumes, _ = split_volume_for_zone(
        total_volume,
        grid_count,
        settings.min_volume,
        settings.max_volume,
    )

    grid_orders = [
        AiOrderAction(
            count_order=1,
            action_type="entry",
            price=price,
            sl=template.sl,
            tp=_tp_for_index(index, tp_levels, template.tp),
            order_type=template.order_type,
            volume=volumes[index],
            expiration_minutes=template.expiration_minutes,
        )
        for index, price in enumerate(grid_prices)
    ]

    logger.info(
        "Aggressive zone grid: %s-%s → %d orders (was %d limit/stop, %d market) at %s",
        zone_low,
        zone_high,
        grid_count,
        len(grid_entries),
        len(market_entries),
        grid_prices,
    )

    return response.model_copy(
        update={"orders": management + market_entries + grid_orders},
    )


def _resolve_zone_bounds(
    response: AiTradeResponse,
    grid_entries: list[AiOrderAction],
    message_text: str | None,
    reference_price: float | None,
) -> tuple[float, float] | None:
    if response.zone_low is not None and response.zone_high is not None:
        low = min(response.zone_low, response.zone_high)
        high = max(response.zone_low, response.zone_high)
        if low != high:
            return low, high

    prices = [item.price for item in grid_entries if item.price is not None]
    if len(prices) >= 2:
        low = min(prices)
        high = max(prices)
        if low != high:
            return low, high

    return parse_zone_bounds(message_text, reference_price)


def _resolve_tp_levels(
    message_text: str | None,
    entries: list[AiOrderAction],
    reference_price: float | None,
) -> list[float]:
    parsed = parse_tp_levels(message_text, reference_price)
    if parsed:
        return parsed

    seen: list[float] = []
    for item in entries:
        if item.tp is None or item.tp in seen:
            continue
        seen.append(item.tp)
    return seen


def _tp_for_index(
    index: int,
    tp_levels: list[float],
    fallback: float | None,
) -> float | None:
    if tp_levels and index < len(tp_levels):
        return tp_levels[index]
    if tp_levels:
        return tp_levels[-1]
    return fallback


def _default_template(
    entries: list[AiOrderAction],
    settings: Settings,
) -> AiOrderAction:
    for item in entries:
        if item.action_type.lower() == "entry":
            return item
    return AiOrderAction(
        count_order=1,
        action_type="entry",
        order_type="limit",
        volume=settings.default_volume,
    )


def _reference_price(
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
