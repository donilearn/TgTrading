from models.chat_message import ChatMessage, MediaAttachment


def is_audio_video(media: MediaAttachment | None) -> bool:
    if media is None:
        return False
    return media.media_type in {"voice", "audio", "video"}


def is_image(media: MediaAttachment | None) -> bool:
    return media is not None and media.media_type == "photo"


def enrich_with_parsed_media(message: ChatMessage, parsed_text: str) -> ChatMessage:
    parts: list[str] = []
    if message.text:
        parts.append(message.text)
    parts.append(f"[Audio/Video transkript]:\n{parsed_text}")
    return message.model_copy(update={
        "text": "\n\n".join(parts),
        "media": None,
    })
