from models.chat_message import ChatMessage


def message_fingerprint(message: ChatMessage) -> str:
    """Kontent fingerprint — faqat matn/media o'zgarganda yangilanadi (edit_date emas)."""
    media_tag = ""
    if message.media is not None:
        media_tag = f"{message.media.media_type}:{message.media.mime_type}:{len(message.media.data)}"
    return "|".join([
        message.text or "",
        media_tag,
    ])
