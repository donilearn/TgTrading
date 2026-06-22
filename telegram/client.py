import asyncio
import logging
import sqlite3

from telethon import TelegramClient

from config.settings import Settings
from telegram.resilient_session import ResilientSQLiteSession

logger = logging.getLogger(__name__)

_DISCONNECT_RETRIES = 3


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = TelegramClient(
            ResilientSQLiteSession(settings.telegram_session_name),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

    @property
    def client(self) -> TelegramClient:
        return self._client

    async def start(self) -> None:
        await self._client.start()
        me = await self._client.get_me()
        logger.info("Telegram connected as %s", me.username or me.id)

    async def stop(self) -> None:
        if not self._client.is_connected():
            return

        for attempt in range(_DISCONNECT_RETRIES):
            try:
                await self._client.disconnect()
                logger.info("Telegram disconnected")
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt >= _DISCONNECT_RETRIES - 1:
                    logger.warning("Telegram disconnect failed: %s", exc)
                    return
                delay = 0.5 * (attempt + 1)
                logger.warning(
                    "Telegram session locked, retrying in %.1fs (%d/%d)",
                    delay,
                    attempt + 1,
                    _DISCONNECT_RETRIES,
                )
                await asyncio.sleep(delay)
            except Exception as exc:
                logger.warning("Telegram disconnect error: %s", exc)
                return
