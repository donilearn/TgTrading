from models.chat_message import ChatMessage


def format_message_for_ai(
    message: ChatMessage,
    *,
    index: int | None = None,
    is_current: bool = False,
    is_edit: bool = False,
) -> str:
    lines: list[str] = []
    if is_current and is_edit:
        header = "EDITED CURRENT MESSAGE"
    elif is_current:
        header = "CURRENT MESSAGE"
    else:
        header = "MESSAGE"
    if index is not None:
        lines.append(f"--- {index}. {header} ---")
    else:
        lines.append(f"--- {header} ---")

    lines.append(f"message_id={message.message_id}")
    lines.append(f"chat_id={message.chat_id}")
    if message.date:
        lines.append(f"time={message.date}")
    lines.append(f"sender={message.sender_display}")
    if message.sender_id is not None:
        lines.append(f"sender_id={message.sender_id}")

    if message.is_channel_post:
        lines.append("kind=channel_post")
    if message.post_author:
        lines.append(f"post_author={message.post_author}")
    if message.forward_from:
        lines.append(f"forward={message.forward_from}")
    if message.entities_note:
        lines.append(f"entities={message.entities_note}")
    if message.edit_date:
        lines.append(f"edited_at={message.edit_date}")

    if message.reply_to:
        lines.append("REPLY_TO (message being replied to):")
        lines.append(f"  reply_msg_id={message.reply_to.message_id}")
        if message.reply_to.date:
            lines.append(f"  reply_time={message.reply_to.date}")
        lines.append(f"  reply_sender={message.reply_to.sender}")
        if message.reply_to.text:
            lines.append(f"  reply_text={message.reply_to.text!r}")
        else:
            lines.append("  reply_text=(empty or media)")

    if message.text:
        lines.append("text:")
        lines.append(message.text)

    if message.media:
        media_hint = _media_hint(message.media.media_type)
        if message.text:
            lines.append(f"media={message.media.media_type}")
        else:
            lines.append(f"text=(none) | media={message.media.media_type}")
        if media_hint:
            lines.append(media_hint)
    elif not message.text:
        lines.append("text=(empty)")

    return "\n".join(lines)


def _media_hint(media_type: str) -> str | None:
    if media_type == "photo":
        return (
            "media_note=chart image attached — read levels, zone, SL/TP and the "
            "latest price line from the image; compare with time="
        )
    return None


def format_context_block(context: list[ChatMessage]) -> str:
    if not context:
        return ""

    blocks = [
        format_message_for_ai(msg, index=i + 1)
        for i, msg in enumerate(context)
    ]
    return "RECENT GROUP MESSAGES (history, oldest → newest):\n\n" + "\n\n".join(blocks)
