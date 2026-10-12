import logging

from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder

logger = logging.getLogger(__name__)

_DIRECTIONS = frozenset({"buy", "sell"})
_FULL_EXIT_TYPES = frozenset({"close", "cancel"})


def find_opposite_orders(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
) -> list[ExistingOrder]:
    """Yangi signal yo'nalishiga qarama-qarshi bo'lgan shu symboldagi orderlar."""
    if not response.is_signal or not response.symbol:
        return []

    side = response.side.lower()
    if side not in _DIRECTIONS:
        return []

    return [
        item for item in existing
        if item.symbol == response.symbol
        and item.side.lower() in _DIRECTIONS
        and item.side.lower() != side
    ]


def without_orders(
    existing: list[ExistingOrder],
    removed: list[ExistingOrder],
) -> list[ExistingOrder]:
    removed_numbers = {item.order_number for item in removed}
    return [item for item in existing if item.order_number not in removed_numbers]


def apply_reversal(
    response: AiTradeResponse,
    opposite: list[ExistingOrder],
) -> AiTradeResponse:
    """
    Kanal yo'nalishni o'zgartirdi (BUY → SELL yoki aksincha):
    eski pozitsiyalar to'liq yopiladi, eski pending lar bekor qilinadi.
    Faqat javobda yangi entry qolgan bo'lsa qo'llanadi.
    """
    if not opposite:
        return response

    has_entries = any(
        item.action_type.lower() == "entry" for item in response.orders
    )
    if not has_entries:
        return response

    already_exiting = {
        str(item.count_order)
        for item in response.orders
        if item.action_type.lower() in _FULL_EXIT_TYPES and item.volume is None
    }

    exits: list[AiOrderAction] = []
    for item in opposite:
        if item.order_number in already_exiting:
            continue
        exits.append(AiOrderAction(
            count_order=int(item.order_number),
            action_type="close" if item.is_position else "cancel",
        ))

    if not exits:
        return response

    exit_numbers = {item.order_number for item in opposite}
    # Qarama-qarshi orderlarga modify/qisman close ma'nosiz — ular yopiladi
    kept = [
        item for item in response.orders
        if item.action_type.lower() == "entry"
        or str(item.count_order) not in exit_numbers
        or (item.action_type.lower() in _FULL_EXIT_TYPES and item.volume is None)
    ]

    logger.info(
        "Reversal %s %s: closing %d opposite order(s) before new entries",
        response.symbol,
        response.side,
        len(exits),
    )
    note = f" [reversal: closed/cancelled {len(exits)} opposite order(s)]"
    return response.model_copy(update={
        "orders": exits + kept,
        "reasoning": (response.reasoning or "") + note,
    })
