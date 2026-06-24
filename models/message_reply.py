from pydantic import BaseModel


class MessageReply(BaseModel):
    """Javob berilgan (reply) xabar ma'lumotlari."""

    message_id: int
    sender: str
    text: str = ""
    date: str | None = None
