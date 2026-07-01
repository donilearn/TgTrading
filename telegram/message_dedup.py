class MessageDedupTracker:
    """Bir xil xabar versiyasini qayta-qayta AI ga yubormaslik uchun."""

    def __init__(self) -> None:
        self._processed: dict[tuple[int, int], str] = {}

    def already_processed(self, chat_id: int, message_id: int, fingerprint: str) -> bool:
        return self._processed.get((chat_id, message_id)) == fingerprint

    def mark_processed(self, chat_id: int, message_id: int, fingerprint: str) -> None:
        self._processed[(chat_id, message_id)] = fingerprint
