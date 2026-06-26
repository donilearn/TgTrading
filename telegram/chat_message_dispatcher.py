import asyncio
import logging
from collections import defaultdict

from models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


class ChatMessageDispatcher:
    """Bitta chat uchun xabarlarni ketma-ket qayta ishlaydi (parallel race oldini oladi)."""

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._pending: dict[int, int] = defaultdict(int)

    async def run_serial(
        self,
        chat_id: int,
        message_id: int,
        handler,
    ) -> None:
        pending = self._pending[chat_id]
        if pending:
            logger.info(
                "Chat %s msg=%s queued — %d handler(s) ahead",
                chat_id,
                message_id,
                pending,
            )

        self._pending[chat_id] += 1
        lock = self._locks[chat_id]
        try:
            async with lock:
                if pending:
                    logger.info(
                        "Chat %s msg=%s processing (waited for %d msg)",
                        chat_id,
                        message_id,
                        pending,
                    )
                await handler()
        finally:
            self._pending[chat_id] = max(0, self._pending[chat_id] - 1)
