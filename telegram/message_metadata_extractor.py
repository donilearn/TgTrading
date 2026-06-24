import logging
from datetime import UTC, datetime
from typing import Any

from telethon import TelegramClient
from telethon.tl.custom.message import Message

from models.message_reply import MessageReply
from telegram.sender_resolver import resolve_sender

logger = logging.getLogger(__name__)


async def extract_reply(client: TelegramClient, message: Message) -> MessageReply | None:
    if not message.is_reply:
        return None

    reply_id = message.reply_to_msg_id
    if reply_id is None:
        return None

    try:
        reply_msg = await message.get_reply_message()
    except Exception:
        logger.debug("Failed to fetch reply message %s", reply_id, exc_info=True)
        reply_msg = None

    if reply_msg is None:
        return MessageReply(
            message_id=reply_id,
            sender="unknown",
            text="(reply xabar olinmadi)",
        )

    try:
        entity = await reply_msg.get_sender()
    except Exception:
        logger.debug(
            "Failed to resolve reply sender for message %s",
            reply_msg.id,
            exc_info=True,
        )
        entity = reply_msg.sender

    reply_sender, _, reply_display = resolve_sender(entity)
    sender_label = _sender_label(reply_sender, reply_display)

    return MessageReply(
        message_id=reply_msg.id,
        sender=sender_label,
        text=reply_msg.raw_text or reply_msg.message or "",
        date=_format_date(reply_msg.date),
    )


def extract_forward_from(message: Message) -> str | None:
    forward = getattr(message, "forward", None)
    if not forward:
        return None

    parts: list[str] = []
    from_name = getattr(forward, "from_name", None)
    if from_name:
        parts.append(str(from_name))

    channel = getattr(forward, "channel_id", None)
    if channel is not None:
        parts.append(f"channel_id={channel}")

    sender = getattr(forward, "from_id", None)
    if sender is not None:
        parts.append(f"from_id={sender}")

    post_author = getattr(message, "post_author", None)
    if post_author:
        parts.append(f"post_author={post_author}")

    return " | ".join(parts) if parts else "forwarded"


def extract_entities_note(message: Message) -> str | None:
    entities = getattr(message, "entities", None) or []
    if not entities:
        return None

    notes: list[str] = []
    for entity in entities:
        name = type(entity).__name__
        if name == "MessageEntityUrl":
            notes.append("url")
        elif name == "MessageEntityTextUrl":
            notes.append("text_url")
        elif name == "MessageEntityMention":
            notes.append("mention")
        elif name == "MessageEntityHashtag":
            notes.append("hashtag")
        elif name == "MessageEntityBold":
            notes.append("bold")
        elif name not in notes:
            notes.append(name.removeprefix("MessageEntity").lower())

    return ", ".join(notes) if notes else None


def extract_post_flags(message: Message) -> tuple[bool, str | None]:
    is_channel_post = bool(getattr(message, "post", False))
    post_author = getattr(message, "post_author", None)
    return is_channel_post, str(post_author) if post_author else None


def _format_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.isoformat()
    return str(value)


def _sender_label(sender: str, display_name: str | None) -> str:
    if display_name and display_name not in sender:
        return f"{sender} ({display_name})"
    return sender
