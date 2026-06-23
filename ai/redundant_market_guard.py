import logging

from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder

logger = logging.getLogger(__name__)


def remove_redundant_market_entries(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
) -> AiTradeResponse:
    """Zone signali kelganda mavjud pozitsiya bo'lsa qo'shimcha market entry ni olib tashlaydi."""
    if not response.is_signal or not response.symbol:
        return response

    side = response.side.lower()
    has_position = any(
        item.is_position
        and item.symbol == response.symbol
        and item.side.lower() == side
        for item in existing
    )
    if not has_position:
        return response

    filtered = []
    skipped_market = False
    for item in response.orders:
        if (
            not skipped_market
            and item.action_type.lower() == "entry"
            and item.order_type.lower() == "market"
        ):
            skipped_market = True
            continue
        filtered.append(item)

    if not skipped_market:
        return response

    logger.info(
        "Skip redundant market entry for %s %s — open position already exists",
        response.symbol,
        side,
    )
    return response.model_copy(update={"orders": filtered})
