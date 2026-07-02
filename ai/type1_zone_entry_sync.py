import logging

from ai.sl_level_parser import parse_sl_level
from ai.tp_order_count import message_tp_levels, reference_price_from_market
from ai.zone_bounds_parser import parse_zone_bounds
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.volume_normalizer import split_volume_for_zone
from trading.zone_price_distribution import evenly_spaced_prices

logger = logging.getLogger(__name__)

_MANAGEMENT_TYPES = frozenset({"close", "cancel"})


def sync_type1_zone_entries(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
    message_text: str | None,
    settings: Settings,
    market: list[SymbolMarketInfo] | None = None,
) -> AiTradeResponse:
    """TYPE 1: zone + ko'p TP — har TP uchun limit entry (mavjud pozitsiya → modify + qolgan limitlar)."""
    if not response.is_signal or not response.symbol:
        return response

    reference_price = reference_price_from_market(response.symbol, market)
    tp_levels = message_tp_levels(message_text, reference_price)
    if len(tp_levels) < 2:
        return response

    zone = _resolve_zone(response, message_text, reference_price)
    if zone is None:
        return response

    zone_low, zone_high = zone
    side = response.side.lower()
    symbol = response.symbol
    sl = _resolve_sl(response, message_text, reference_price)
    volume = settings.default_volume

    positions = [
        item for item in existing
        if item.is_position
        and item.symbol == symbol
        and item.side.lower() == side
    ]

    management = [
        item for item in response.orders
        if item.action_type.lower() in _MANAGEMENT_TYPES
    ]

    prices = evenly_spaced_prices(zone_low, zone_high, len(tp_levels))
    expiration = settings.orders_expiration_minutes or None

    orders: list[AiOrderAction] = list(management)

    if positions:
        modify_target = _modify_target(response.orders, positions)
        orders.append(
            AiOrderAction(
                count_order=modify_target,
                action_type="modify",
                sl=sl,
                tp=tp_levels[0],
                order_type="market",
            )
        )
        # Market allaqachon ochilgan — zonadagi BARCHA limitlar (4075 va 4080) ochiladi
        entry_tps = tp_levels
        entry_prices = prices
    else:
        entry_tps = tp_levels
        entry_prices = prices

    if entry_tps:
        volumes, _ = split_volume_for_zone(
            volume * len(entry_tps),
            len(entry_tps),
            settings.min_volume,
            settings.max_volume,
        )
        for index, (price, tp) in enumerate(zip(entry_prices, entry_tps)):
            if _has_pending_near(existing, symbol, side, price):
                continue
            orders.append(
                AiOrderAction(
                    count_order=1,
                    action_type="entry",
                    price=price,
                    sl=sl,
                    tp=tp,
                    order_type="limit",
                    volume=volumes[index],
                    expiration_minutes=expiration,
                )
            )

    limit_count = sum(1 for o in orders if o.action_type.lower() == "entry")
    logger.info(
        "TYPE1 zone sync: %s %s zone=%s-%s TP=%d → modify=%d limit=%d",
        symbol,
        side,
        zone_low,
        zone_high,
        len(tp_levels),
        1 if positions else 0,
        limit_count,
    )

    return response.model_copy(
        update={
            "zone_low": zone_low,
            "zone_high": zone_high,
            "orders": orders,
        },
    )


def _resolve_zone(
    response: AiTradeResponse,
    message_text: str | None,
    reference_price: float | None,
) -> tuple[float, float] | None:
    if response.zone_low is not None and response.zone_high is not None:
        low = min(response.zone_low, response.zone_high)
        high = max(response.zone_low, response.zone_high)
        if low != high:
            return low, high

    return parse_zone_bounds(message_text, reference_price)


def _resolve_sl(
    response: AiTradeResponse,
    message_text: str | None,
    reference_price: float | None,
) -> float | None:
    parsed = parse_sl_level(message_text, reference_price)
    if parsed is not None:
        return parsed

    for item in response.orders:
        if item.sl is not None:
            return item.sl

    return None


def _modify_target(
    orders: list[AiOrderAction],
    positions: list[ExistingOrder],
) -> int:
    for item in orders:
        if item.action_type.lower() == "modify":
            return item.count_order

    return int(positions[0].order_number)


def _has_pending_near(
    existing: list[ExistingOrder],
    symbol: str,
    side: str,
    price: float,
    tolerance: float = 0.5,
) -> bool:
    for item in existing:
        if item.is_position:
            continue
        if item.symbol != symbol:
            continue
        if item.side.lower() != side.lower():
            continue
        if abs(item.open_price - price) <= tolerance:
            return True
    return False
