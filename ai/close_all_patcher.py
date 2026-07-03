import logging

from ai.close_all_detector import message_asks_close_all
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder

logger = logging.getLogger(__name__)


def apply_close_all_from_message(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
    message_text: str | None,
) -> AiTradeResponse:
    """YOPING / close all — guruhdagi barcha pozitsiya va pending ni yopish."""
    if not message_asks_close_all(message_text):
        return response

    symbol = response.symbol
    targets = _filter_targets(existing, symbol)
    if not targets:
        logger.info("Close-all: no open orders (symbol=%s)", symbol or "any")
        return AiTradeResponse(
            is_signal=False,
            reasoning="Close-all: no open orders",
        )

    close_orders = [
        AiOrderAction(
            count_order=int(item.order_number),
            action_type="close",
        )
        for item in targets
    ]
    resolved_symbol = symbol or targets[0].symbol
    side = response.side if response.side and response.side.lower() != "none" else targets[0].side

    logger.info(
        "Close-all patch: %d order(s) symbol=%s",
        len(close_orders),
        resolved_symbol,
    )
    return AiTradeResponse(
        is_signal=True,
        symbol=resolved_symbol,
        side=side.lower(),
        orders=close_orders,
        reasoning="Close all — positions + pending",
    )


def _filter_targets(
    existing: list[ExistingOrder],
    symbol: str | None,
) -> list[ExistingOrder]:
    if not symbol:
        return list(existing)
    return [item for item in existing if item.symbol == symbol]
