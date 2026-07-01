import logging
from collections.abc import Awaitable, Callable

from telethon import events
from telethon.tl.custom.message import Message

from models.chat_message import ChatMessage
from telegram.chat_message_dispatcher import ChatMessageDispatcher
from telegram.client import TelegramService
from telegram.media_extractor import build_chat_message, build_sender_info
from telegram.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)

MessageHandler = Callable[..., Awaitable[None]]


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
        self._chat_titles: dict[int, str] = {}
        self._dispatcher = ChatMessageDispatcher()

    async def _resolve_chat_title(self, chat_id: int) -> str:
        if chat_id in self._chat_titles:
            return self._chat_titles[chat_id]

        entity = await self._telegram.client.get_entity(chat_id)
        title = (
            getattr(entity, "title", None)
            or getattr(entity, "username", None)
            or str(chat_id)
        )
        self._chat_titles[chat_id] = title
        return title

    async def _build_message(self, raw: Message, chat_id: int) -> ChatMessage:
        client = self._telegram.client
        sender, sender_id, sender_display = await build_sender_info(client, raw)
        chat_title = await self._resolve_chat_title(chat_id)
        return await build_chat_message(
            client,
            raw,
            chat_id,
            sender,
            sender_id=sender_id,
            sender_display=sender_display,
            chat_title=chat_title,
        )

    async def _dispatch(
        self,
        chat_id: int,
        message: ChatMessage,
        *,
        is_edit: bool,
    ) -> None:
        media_tag = f" +{message.media.media_type}" if message.media else ""
        if is_edit:
            logger.info(
                "Edited message in chat %s msg=%s from %s%s",
                chat_id,
                message.message_id,
                message.sender,
                media_tag,
            )
        else:
            logger.info(
                "New message in chat %s msg=%s from %s%s",
                chat_id,
                message.message_id,
                message.sender,
                media_tag,
            )

        async def _handle() -> None:
            if is_edit:
                context = self._buffer.get_context_excluding(
                    chat_id,
                    message.message_id,
                )
            else:
                context = self._buffer.get_context(chat_id)

            await self._on_message(message, context, is_edit=is_edit)

            if is_edit:
                self._buffer.upsert(message)
            else:
                self._buffer.add(message)

        await self._dispatcher.run_serial(
            chat_id,
            message.message_id,
            _handle,
        )

    def register(self) -> None:
        client = self._telegram.client

        @client.on(events.NewMessage(chats=self._group_ids))
        async def on_new_message(event: events.NewMessage.Event) -> None:
            message = await self._build_message(event.message, event.chat_id)
            await self._dispatch(event.chat_id, message, is_edit=False)

        @client.on(events.MessageEdited(chats=self._group_ids))
        async def on_edited_message(event: events.MessageEdited.Event) -> None:
            message = await self._build_message(event.message, event.chat_id)
            await self._dispatch(event.chat_id, message, is_edit=True)

        logger.info(
            "Listening to %d group(s): %s (new + edited)",
            len(self._group_ids),
            self._group_ids,
        )
