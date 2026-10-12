import logging

from models.ai_order_action import AiOrderAction
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo

logger = logging.getLogger(__name__)


def plan_deleted_signal_actions(
    targets: list[ExistingOrder],
    market: list[SymbolMarketInfo],
) -> list[AiOrderAction]:
    """
    Kanal signal xabarini o'chirdi:
    - pending (limit/stop) → cancel
    - profitdagi pozitsiya → SL = openPrice (breakeven)
    - zarardagi pozitsiya → tegilmaydi (o'z SL i bilan qoladi)
    """
    quotes = {item.symbol: item for item in market}
    actions: list[AiOrderAction] = []

    for order in targets:
        if not order.is_position:
            actions.append(AiOrderAction(
                count_order=int(order.order_number),
                action_type="cancel",
            ))
            continue

        quote = quotes.get(order.symbol)
        if not _in_profit(order, quote):
            logger.info(
                "Deleted signal: #%s %s not in profit — left unchanged",
                order.order_number,
                order.symbol,
            )
            continue
        if not _sl_below_breakeven(order):
            continue

        actions.append(AiOrderAction(
            count_order=int(order.order_number),
            action_type="modify",
            sl=order.open_price,
            tp=None,
        ))

    return actions


def _in_profit(order: ExistingOrder, quote: SymbolMarketInfo | None) -> bool:
    if quote is None:
        return False
    side = order.side.lower()
    if side == "buy" and quote.bid is not None:
        return quote.bid > order.open_price
    if side == "sell" and quote.ask is not None:
        return quote.ask < order.open_price
    return False


def _sl_below_breakeven(order: ExistingOrder) -> bool:
    """SL hali breakeven dan yomonroq joydami (BE kerakmi)."""
    if order.stop_loss is None:
        return True
    side = order.side.lower()
    if side == "buy":
        return order.stop_loss < order.open_price
    if side == "sell":
        return order.stop_loss > order.open_price
    return False
