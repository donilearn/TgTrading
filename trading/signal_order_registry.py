import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_MESSAGES_PER_CHAT = 500


class SignalOrderRegistry:
    """Telegram xabar (chat_id, message_id) → shu xabardan ochilgan broker ticketlar."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._data: dict[str, dict[str, list[str]]] = {}
        self._load()

    def record(self, chat_id: int, message_id: int, order_ids: list[str]) -> None:
        if not order_ids:
            return
        chat = self._data.setdefault(str(chat_id), {})
        tickets = chat.setdefault(str(message_id), [])
        for order_id in order_ids:
            if order_id not in tickets:
                tickets.append(order_id)
        self._trim(chat)
        self._save()

    def tickets_for(self, chat_id: int, message_ids: list[int]) -> set[str]:
        chat = self._data.get(str(chat_id), {})
        tickets: set[str] = set()
        for message_id in message_ids:
            tickets.update(chat.get(str(message_id), []))
        return tickets

    def forget(self, chat_id: int, message_ids: list[int]) -> None:
        chat = self._data.get(str(chat_id))
        if not chat:
            return
        removed = False
        for message_id in message_ids:
            removed = chat.pop(str(message_id), None) is not None or removed
        if removed:
            self._save()

    @staticmethod
    def _trim(chat: dict[str, list[str]]) -> None:
        # dict insertion tartibini saqlaydi — eng eski xabarlar birinchi o'chadi
        while len(chat) > _MAX_MESSAGES_PER_CHAT:
            chat.pop(next(iter(chat)))

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Signal registry load failed (%s): %s", self._path, exc)
            return
        if isinstance(raw, dict):
            self._data = {
                str(chat_id): {str(msg_id): [str(t) for t in tickets] for msg_id, tickets in chat.items()}
                for chat_id, chat in raw.items()
                if isinstance(chat, dict)
            }

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as exc:
            logger.warning("Signal registry save failed (%s): %s", self._path, exc)
