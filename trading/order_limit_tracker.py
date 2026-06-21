import logging

logger = logging.getLogger(__name__)


class OrderLimitTracker:
    def __init__(self, max_orders: int, max_per_group: int) -> None:
        self._max_orders = max_orders
        self._max_per_group = max_per_group
        self._global_count = 0

    def can_place(
        self,
        chat_id: int,
        order_count: int,
        existing_count: int = 0,
    ) -> tuple[bool, str, int]:
        """Return (allowed, message, max_to_place). Uses broker order count as source of truth."""
        group_remaining = max(0, self._max_per_group - existing_count)
        global_remaining = max(0, self._max_orders - existing_count)

        remaining = min(group_remaining, global_remaining)
        if remaining <= 0:
            return False, (
                f"Group {chat_id} limit reached "
                f"({existing_count}/{self._max_per_group})"
            ), 0

        if order_count > remaining:
            return True, (
                f"Group {chat_id}: planned {order_count}, "
                f"placing {remaining} ({existing_count}/{self._max_per_group} used)"
            ), remaining

        return True, "", order_count

    def record(self, chat_id: int, order_count: int = 1) -> None:
        self._global_count += order_count
        logger.info(
            "Orders placed: group %s +%d, global session +%d/%d",
            chat_id,
            order_count,
            self._global_count,
            self._max_orders,
        )
