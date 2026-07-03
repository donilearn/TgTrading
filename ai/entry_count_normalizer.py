import logging

from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse

logger = logging.getLogger(__name__)


def normalize_entry_count_orders(response: AiTradeResponse) -> AiTradeResponse:
    """Entry uchun countOrder har doim 1 — AI 1,2,3 ketma-ket raqam yuborsa ham."""
    changed = False
    updated: list[AiOrderAction] = []

    for item in response.orders:
        if item.action_type.lower() != "entry":
            updated.append(item)
            continue
        if item.count_order != 1:
            changed = True
            updated.append(item.model_copy(update={"count_order": 1}))
        else:
            updated.append(item)

    if not changed:
        return response

    logger.info("Normalized entry countOrder → 1 for all entry orders")
    return response.model_copy(update={"orders": updated})
