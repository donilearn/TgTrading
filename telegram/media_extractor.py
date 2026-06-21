import logging

from telethon import TelegramClient
from telethon.tl.custom.message import Message

from models.chat_message import ChatMessage, MediaAttachment

logger = logging.getLogger(__name__)

PHOTO_MIME = "image/jpeg"
VOICE_MIME = "audio/ogg"
AUDIO_MIME = "audio/mpeg"


async def build_chat_message(
    client: TelegramClient,
    message: Message,
    chat_id: int,
    sender: str,
) -> ChatMessage:
    text = message.raw_text or message.message or ""
    media = await _extract_media(client, message)

    return ChatMessage(
        chat_id=chat_id,
        message_id=message.id,
        sender=sender,
        text=text,
        media=media,
    )


async def _extract_media(
    client: TelegramClient,
    message: Message,
) -> MediaAttachment | None:
    try:
        if message.photo:
            data = await client.download_media(message, bytes)
            if data:
                return MediaAttachment(
                    mime_type=PHOTO_MIME,
                    data=data,
                    media_type="photo",
                )

        if message.voice:
            data = await client.download_media(message, bytes)
            if data:
                return MediaAttachment(
                    mime_type=VOICE_MIME,
                    data=data,
                    media_type="voice",
                )

        if message.audio:
            data = await client.download_media(message, bytes)
            if data:
                mime = getattr(message.audio, "mime_type", None) or AUDIO_MIME
                return MediaAttachment(
                    mime_type=mime,
                    data=data,
                    media_type="audio",
                )

    except Exception:
        logger.exception("Failed to download media for message %s", message.id)

    return None
