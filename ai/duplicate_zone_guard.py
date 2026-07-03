import logging

from ai.pending_price_guard import has_pending_near_price
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder

logger = logging.getLogger(__name__)

_ENTRY_TYPES = frozenset({"limit", "stop"})


def remove_duplicate_zone_entries(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
    *,
    price_tolerance: float = 0.5,
) -> AiTradeResponse:
    """Allaqachon pending bo'lgan narxda limit qayta ochilmasin (emoji spam)."""
    if not response.is_signal or not response.symbol:
        return response

    symbol = response.symbol
    side = response.side.lower()
    if side not in ("buy", "sell"):
        return response

    filtered = []
    skipped = 0
    for item in response.orders:
        if item.action_type.lower() != "entry":
            filtered.append(item)
            continue
        if item.order_type.lower() not in _ENTRY_TYPES:
            filtered.append(item)
            continue
        if item.price is None:
            filtered.append(item)
            continue
        if has_pending_near_price(
            existing, symbol, side, item.price, price_tolerance,
        ):
            skipped += 1
            continue
        filtered.append(item)

    if skipped == 0:
        return response

    entries_left = [
        o for o in filtered if o.action_type.lower() == "entry"
    ]
    management_left = [
        o for o in filtered if o.action_type.lower() != "entry"
    ]

    logger.info(
        "Duplicate zone guard: skipped %d limit(s) at existing prices for %s %s",
        skipped,
        symbol,
        side,
    )

    if not entries_left and not management_left:
        return response.model_copy(
            update={
                "is_signal": False,
                "orders": [],
                "reasoning": (response.reasoning or "") + " [all limits duplicate]",
            },
        )

    return response.model_copy(update={"orders": filtered})
