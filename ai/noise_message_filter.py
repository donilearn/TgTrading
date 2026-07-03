import logging
import re

from ai.close_all_detector import message_asks_close_all
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder

logger = logging.getLogger(__name__)

_DIRECTION_HINT = re.compile(
    r"\b(buy|sell|long|short|gold\s+sell|gold\s+buy|entry|sl|tp)\b",
    re.IGNORECASE,
)
_NOISE_WORDS = frozenset({
    "bum", "ok", "lol", "haha", "nice", "gg", "wow", "damn", "fire",
    "done", "hit", "profit", "running",
})


def is_reaction_noise(message_text: str | None) -> bool:
    """Emoji/reaction xabar — yangi entry ochmaslik kerak."""
    if not message_text or not message_text.strip():
        return False

    stripped = message_text.strip()
    if _DIRECTION_HINT.search(stripped):
        return False

    alpha = re.sub(r"[^\w\s]", "", stripped, flags=re.UNICODE)
    alpha = re.sub(r"\s+", " ", alpha).strip().lower()
    if not alpha:
        return True

    words = alpha.split()
    if len(words) == 1 and words[0] in _NOISE_WORDS:
        return True
    if len(alpha) <= 3 and words[0] not in {"buy", "sell"}:
        return True

    return False


def suppress_noise_entries(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
    message_text: str | None,
) -> AiTradeResponse:
    """AI noto'g'ri signal deb qaytarsa — reaction xabarda entry ochilmasin."""
    if not response.is_signal:
        return response
    if message_asks_close_all(message_text):
        return response
    if not is_reaction_noise(message_text):
        return response

    has_entries = any(
        item.action_type.lower() == "entry" for item in response.orders
    )
    if not has_entries:
        return response

    if existing:
        logger.info(
            "Noise suppressed — %d existing order(s), skipping new entries",
            len(existing),
        )
    else:
        logger.info("Noise suppressed — reaction message, not a signal")

    return AiTradeResponse(
        is_signal=False,
        reasoning="Reaction/noise message — not a trade signal",
    )
