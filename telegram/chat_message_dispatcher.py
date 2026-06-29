import asyncio
import logging

logger = logging.getLogger(__name__)


class ChatMessageDispatcher:
    """Bitta chat uchun xabarlarni ketma-ket qayta ishlaydi (parallel race oldini oladi)."""

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()
        self._pending: dict[int, int] = {}

    async def _lock_for(self, chat_id: int) -> asyncio.Lock:
        """Har chat_id uchun bitta Lock — yaralish race ini meta-lock bilan himoya qiladi."""
        async with self._meta_lock:
            lock = self._locks.get(chat_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[chat_id] = lock
            return lock

    async def run_serial(
        self,
        chat_id: int,
        message_id: int,
        handler,
    ) -> None:
        lock = await self._lock_for(chat_id)

        pending = self._pending.get(chat_id, 0)
        if pending:
            logger.info(
                "Chat %s msg=%s queued — %d handler(s) ahead",
                chat_id,
                message_id,
                pending,
            )

        self._pending[chat_id] = pending + 1
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
            self._pending[chat_id] = max(0, self._pending.get(chat_id, 1) - 1)
