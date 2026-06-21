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

    def add(self, message: ChatMessage) -> None:
        if message.chat_id not in self._buffers:
            self._buffers[message.chat_id] = deque(maxlen=self._max_size)
        self._buffers[message.chat_id].append(message)
