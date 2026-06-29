import logging

logger = logging.getLogger(__name__)


class OrderLimitTracker:
    def __init__(self, max_per_channel: int, max_per_message: int) -> None:
        self._max_per_channel = max_per_channel
        self._max_per_message = max_per_message
        self._session_count = 0

    def can_place(
        self,
        chat_id: int,
        order_count: int,
        existing_channel_count: int,
        *,
        msg_tp_count: int | None = None,
    ) -> tuple[bool, str, int]:
        """Cap per channel (MAX_ORDER_COUNT). Xabar TP lari bo'lsa per-msg limit o'tkaziladi."""
        channel_remaining = max(0, self._max_per_channel - existing_channel_count)
        if msg_tp_count and msg_tp_count > 0:
            msg_cap = msg_tp_count
        else:
            msg_cap = max(0, self._max_per_message)

        remaining = min(order_count, msg_cap, channel_remaining)

        if remaining <= 0:
            return False, (
                f"Channel {chat_id} limit reached "
                f"(channel {existing_channel_count}/{self._max_per_channel}, "
                f"msg max {self._max_per_message})"
            ), 0

        if order_count > remaining:
            limit_label = (
                f"msg TP count {msg_tp_count}"
                if msg_tp_count
                else f"msg max {self._max_per_message}"
            )
            return True, (
                f"Channel {chat_id}: planned {order_count}, placing {remaining} "
                f"({limit_label}, "
                f"channel {existing_channel_count}/{self._max_per_channel})"
            ), remaining

        return True, "", remaining

    def record(self, chat_id: int, order_count: int = 1) -> None:
        self._session_count += order_count
        logger.info(
            "Orders placed: channel %s +%d, session +%d",
            chat_id,
            order_count,
            self._session_count,
        )
