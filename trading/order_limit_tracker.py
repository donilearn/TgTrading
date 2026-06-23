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
        existing_group_count: int,
        existing_global_count: int,
        max_per_message: int,
    ) -> tuple[bool, str, int]:
        """Cap per message, per group (env), and global (env)."""
        group_remaining = max(0, self._max_per_group - existing_group_count)
        global_remaining = max(0, self._max_orders - existing_global_count)
        msg_cap = max(0, max_per_message)

        remaining = min(order_count, msg_cap, group_remaining, global_remaining)

        if remaining <= 0:
            return False, (
                f"Group {chat_id} limit reached "
                f"(group {existing_group_count}/{self._max_per_group}, "
                f"global {existing_global_count}/{self._max_orders}, "
                f"msg max {max_per_message})"
            ), 0

        if order_count > remaining:
            return True, (
                f"Group {chat_id}: planned {order_count}, placing {remaining} "
                f"(msg max {max_per_message}, "
                f"group {existing_group_count}/{self._max_per_group}, "
                f"global {existing_global_count}/{self._max_orders})"
            ), remaining

        return True, "", remaining

    def record(self, chat_id: int, order_count: int = 1) -> None:
        self._global_count += order_count
        logger.info(
            "Orders placed: group %s +%d, session +%d",
            chat_id,
            order_count,
            self._global_count,
        )
