import logging
from collections.abc import Awaitable, Callable

from telethon import events

from models.chat_message import ChatMessage
from telegram.client import TelegramService
from telegram.media_extractor import build_chat_message, build_sender_info
from telegram.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)

MessageHandler = Callable[[ChatMessage, list[ChatMessage]], Awaitable[None]]


class MessageListener:
    def __init__(
        self,
        telegram_service: TelegramService,
        group_ids: list[int],
        message_buffer: MessageBuffer,
        on_message: MessageHandler,
    ) -> None:
        self._telegram = telegram_service
        self._group_ids = group_ids
        self._buffer = message_buffer
        self._on_message = on_message

    def register(self) -> None:
        client = self._telegram.client

        @client.on(events.NewMessage(chats=self._group_ids))
        async def handler(event: events.NewMessage.Event) -> None:
            chat_id = event.chat_id
            sender, sender_id, sender_display = await build_sender_info(
                client,
                event.message,
            )

            chat = await event.get_chat()
            channel_name = getattr(chat, "title", None) or str(chat_id)

            context = self._buffer.get_context(chat_id)

            message = await build_chat_message(
                client,
                event.message,
                chat_id,
                sender,
                sender_id=sender_id,
                sender_display=sender_display,
                channel_name=channel_name,
            )

            media_tag = f" +{message.media.media_type}" if message.media else ""
            logger.info(
                "New message in chat %s from %s%s",
                chat_id,
                sender,
                media_tag,
            )

            await self._on_message(message, context)
            self._buffer.add(message)

        logger.info(
            "Listening to %d group(s): %s",
            len(self._group_ids),
            self._group_ids,
        )
