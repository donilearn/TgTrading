from pydantic import BaseModel, Field

from models.message_reply import MessageReply


class MediaAttachment(BaseModel):
    mime_type: str
    data: bytes
    media_type: str = Field(description="photo, voice, or audio")


class ChatMessage(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    chat_id: int
    message_id: int
    sender: str
    text: str = ""
    media: MediaAttachment | None = None
    sender_id: int | None = None
    sender_display: str = ""
    date: str | None = None
    edit_date: str | None = None
    reply_to: MessageReply | None = None
    forward_from: str | None = None
    is_channel_post: bool = False
    post_author: str | None = None
    entities_note: str | None = None

    @property
    def has_media(self) -> bool:
        return self.media is not None

    def format_for_context(self) -> str:
        """Eski API — qisqa format (ichki fallback)."""
        parts = [f"[{self.sender_display or self.sender}]"]
        if self.date:
            parts.append(f"({self.date})")
        if self.reply_to:
            parts.append(
                f"[reply→{self.reply_to.sender}: {self.reply_to.text[:120]}]",
            )
        if self.text:
            parts.append(self.text)
        if self.media:
            parts.append(f"({self.media.media_type} attached)")
        return " ".join(parts)
