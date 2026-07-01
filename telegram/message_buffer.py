from collections import deque

from models.chat_message import ChatMessage


class MessageBuffer:
    def __init__(self, max_size: int = 5) -> None:
        self._max_size = max_size
        self._buffers: dict[int, deque[ChatMessage]] = {}

    def get_context(self, chat_id: int) -> list[ChatMessage]:
        buffer = self._buffers.get(chat_id)
        if not buffer:
            return []
        return list(buffer)

    def get_context_excluding(self, chat_id: int, message_id: int) -> list[ChatMessage]:
        return [
            msg for msg in self.get_context(chat_id)
            if msg.message_id != message_id
        ]

    def add(self, message: ChatMessage) -> None:
        if message.chat_id not in self._buffers:
            self._buffers[message.chat_id] = deque(maxlen=self._max_size)
        self._buffers[message.chat_id].append(message)

    def upsert(self, message: ChatMessage) -> bool:
        """Mavjud message_id ni yangilaydi yoki qo'shadi. True = yangilandi."""
        buffer = self._buffers.get(message.chat_id)
        if buffer:
            for index, item in enumerate(buffer):
                if item.message_id == message.message_id:
                    buffer[index] = message
                    return True
        self.add(message)
        return False
