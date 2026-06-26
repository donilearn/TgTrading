import logging

from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder

logger = logging.getLogger(__name__)


def patch_existing_positions_sltp(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
) -> AiTradeResponse:
    """Signalda SL/TP berilsa mavjud pozitsiya/pending orderlarni yangilaydi."""
    if not response.is_signal or not response.symbol:
        return response

    sl, tp = _signal_sltp(response.orders)
    if sl is None and tp is None:
        return response

    side = response.side.lower()
    modify_orders: list[AiOrderAction] = []

    for item in existing:
        if item.symbol != response.symbol:
            continue
        if item.side.lower() != side:
            continue
        if _has_modify_for(response.orders, item.order_number):
            continue

        new_sl = sl
        new_tp = tp
        if new_sl is None and new_tp is None:
            continue

        modify_orders.append(
            AiOrderAction(
                count_order=int(item.order_number),
                action_type="modify",
                sl=new_sl,
                tp=new_tp,
            )
        )

    if not modify_orders:
        return response

    logger.info(
        "Patch existing SL/TP: %d modify order(s) for %s (sl=%s tp=%s)",
        len(modify_orders),
        response.symbol,
        sl,
        tp,
    )
    return response.model_copy(update={"orders": modify_orders + response.orders})


def _signal_sltp(orders: list[AiOrderAction]) -> tuple[float | None, float | None]:
    for item in orders:
        if item.action_type.lower() != "entry":
            continue
        if item.sl is not None or item.tp is not None:
            return item.sl, item.tp
    return None, None


def _has_modify_for(orders: list[AiOrderAction], order_number: str) -> bool:
    target = int(order_number)
    for item in orders:
        if item.action_type.lower() != "modify":
            continue
        if item.count_order == target:
            return True
    return False
