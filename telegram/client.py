import logging

from telethon import TelegramClient

from config.settings import Settings

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = TelegramClient(
            settings.telegram_session_name,
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
        if self._client.is_connected():
            await self._client.disconnect()
            logger.info("Telegram disconnected")
