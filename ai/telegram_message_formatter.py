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
        header = "TAHRIRLANGAN JORIY XABAR"
    elif is_current:
        header = "JORIY XABAR"
    else:
        header = "XABAR"
    if index is not None:
        lines.append(f"--- {index}. {header} ---")
    else:
        lines.append(f"--- {header} ---")

    lines.append(f"message_id={message.message_id}")
    lines.append(f"chat_id={message.chat_id}")
    if message.date:
        lines.append(f"vaqt={message.date}")
    lines.append(f"yuboruvchi={message.sender_display}")
    if message.sender_id is not None:
        lines.append(f"sender_id={message.sender_id}")

    if message.is_channel_post:
        lines.append("turi=kanal_post")
    if message.post_author:
        lines.append(f"post_author={message.post_author}")
    if message.forward_from:
        lines.append(f"forward={message.forward_from}")
    if message.entities_note:
        lines.append(f"entities={message.entities_note}")
    if message.edit_date:
        lines.append(f"tahrirlangan={message.edit_date}")

    if message.reply_to:
        lines.append("REPLY (javob berilgan xabar):")
        lines.append(f"  reply_msg_id={message.reply_to.message_id}")
        if message.reply_to.date:
            lines.append(f"  reply_vaqt={message.reply_to.date}")
        lines.append(f"  reply_yuboruvchi={message.reply_to.sender}")
        if message.reply_to.text:
            lines.append(f"  reply_matn={message.reply_to.text!r}")
        else:
            lines.append("  reply_matn=(bo'sh yoki media)")

    if message.text:
        lines.append("matn:")
        lines.append(message.text)

    if message.media:
        media_hint = _media_hint(message.media.media_type)
        if message.text:
            lines.append(f"media={message.media.media_type}")
        else:
            lines.append(f"matn=(yo'q) | media={message.media.media_type}")
        if media_hint:
            lines.append(media_hint)
    elif not message.text:
        lines.append("matn=(bo'sh)")

    return "\n".join(lines)


def _media_hint(media_type: str) -> str | None:
    if media_type == "photo":
        return (
            "media_eslatma=chart rasm — levellar, zone, SL/TP, "
            "oxirgi (latest) narx chizig'ini rasm ichidan o'qi; "
            "vaqt= bilan solishtir"
        )
    return None


def format_context_block(context: list[ChatMessage]) -> str:
    if not context:
        return ""

    blocks = [
        format_message_for_ai(msg, index=i + 1)
        for i, msg in enumerate(context)
    ]
    return "Oxirgi guruh xabarlari (to'liq kontekst, eskidan yangiga):\n\n" + "\n\n".join(blocks)
