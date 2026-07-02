import logging
import re

from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder
from trading.volume_normalizer import round_volume

logger = logging.getLogger(__name__)

_PARTIAL_CLOSE = re.compile(
    r"secure\s+half|half\s+close|close\s+half|save\s+half|"
    r"yarmini\s+yop|qisman\s+yop|50\s*%\s*(close|save|yop)|"
    r"partial\s+close|partial\s+save",
    re.IGNORECASE,
)


def message_asks_partial_close(message_text: str | None) -> bool:
    if not message_text:
        return False
    return bool(_PARTIAL_CLOSE.search(message_text))


def apply_partial_close_from_message(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
    message_text: str | None,
    settings: Settings,
) -> AiTradeResponse:
    """'Secure half' kabi xabarda AI close qaytarmasa — pozitsiyaning yarmi."""
    if not message_asks_partial_close(message_text):
        return response

    positions = [item for item in existing if item.is_position]
    if not positions:
        return response

    if _has_partial_close_orders(response.orders):
        return response

    symbol = response.symbol or positions[0].symbol
    side = response.side if response.side and response.side != "none" else positions[0].side

    close_orders: list[AiOrderAction] = []
    for position in positions:
        if position.symbol != symbol:
            continue
        close_volume = _half_close_volume(position.volume, settings.min_volume)
        if close_volume is None:
            continue
        close_orders.append(
            AiOrderAction(
                count_order=int(position.order_number),
                action_type="close",
                volume=close_volume,
            ),
        )

    if not close_orders:
        return response

    logger.info(
        "Partial close patch: %s — %d position(s), vol~half",
        symbol,
        len(close_orders),
    )
    return response.model_copy(
        update={
            "is_signal": True,
            "symbol": symbol,
            "side": side.lower(),
            "orders": close_orders + list(response.orders),
        },
    )


def _has_partial_close_orders(orders: list[AiOrderAction]) -> bool:
    for item in orders:
        if item.action_type.lower() != "close":
            continue
        if item.volume is not None and item.volume > 0:
            return True
    return False


def _half_close_volume(
    position_volume: float | None,
    min_volume: float,
) -> float | None:
    if position_volume is None or position_volume <= 0:
        return None

    half = round_volume(position_volume / 2.0)
    if half < min_volume:
        return None
    if half >= position_volume - 1e-9:
        return None

    return half
