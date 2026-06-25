import logging
from datetime import UTC, datetime

from telethon import TelegramClient
from telethon.tl.custom.message import Message

from models.chat_message import ChatMessage, MediaAttachment
from telegram.message_metadata_extractor import (
    extract_entities_note,
    extract_forward_from,
    extract_post_flags,
    extract_reply,
)
from telegram.sender_resolver import resolve_sender

logger = logging.getLogger(__name__)

PHOTO_MIME = "image/jpeg"
VOICE_MIME = "audio/ogg"
AUDIO_MIME = "audio/mpeg"
VIDEO_MIME = "video/mp4"


async def build_chat_message(
    client: TelegramClient,
    message: Message,
    chat_id: int,
    sender: str,
    sender_id: int | None = None,
    sender_display: str | None = None,
    chat_title: str = "",
) -> ChatMessage:
    text = message.raw_text or message.message or ""
    media = await _extract_media(client, message)
    reply_to = await extract_reply(client, message)
    is_channel_post, post_author = extract_post_flags(message)

    display = sender_display or sender
    if sender_display and sender_display not in sender:
        display = f"{sender} ({sender_display})"

    return ChatMessage(
        chat_id=chat_id,
        message_id=message.id,
        sender=sender,
        sender_id=sender_id,
        sender_display=display,
        text=text,
        media=media,
        date=_format_date(message.date),
        edit_date=_format_date(getattr(message, "edit_date", None)),
        reply_to=reply_to,
        forward_from=extract_forward_from(message),
        is_channel_post=is_channel_post,
        post_author=post_author,
        entities_note=extract_entities_note(message),
        chat_title=chat_title,
    )


async def build_sender_info(client: TelegramClient, message: Message) -> tuple[str, int | None, str | None]:
    try:
        entity = await message.get_sender()
    except Exception:
        logger.debug("Failed to resolve sender for message %s", message.id, exc_info=True)
        entity = message.sender

    return resolve_sender(entity)


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

        if message.video:
            data = await client.download_media(message, bytes)
            if data:
                mime = getattr(message.video, "mime_type", None) or VIDEO_MIME
                return MediaAttachment(
                    mime_type=mime,
                    data=data,
                    media_type="video",
                )

    except Exception:
        logger.exception("Failed to download media for message %s", message.id)

    return None


def _format_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.isoformat()
    return str(value)
