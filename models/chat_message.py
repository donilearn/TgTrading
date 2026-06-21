from pydantic import BaseModel, Field


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

    @property
    def has_media(self) -> bool:
        return self.media is not None

    def format_for_context(self) -> str:
        parts = [f"[{self.sender}]"]
        if self.text:
            parts.append(self.text)
        if self.media:
            parts.append(f"({self.media.media_type} attached)")
        return " ".join(parts)
