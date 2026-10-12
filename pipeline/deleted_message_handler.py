import logging
from collections.abc import Awaitable, Callable
from typing import Any

from config.settings import Settings
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from pipeline.deleted_signal_planner import plan_deleted_signal_actions
from trading.ai_order_executor import AiOrderExecutor
from trading.signal_order_registry import SignalOrderRegistry

logger = logging.getLogger(__name__)

ContextLoader = Callable[
    [int, int],
    Awaitable[tuple[list[ExistingOrder], list[SymbolMarketInfo]]],
]


class DeletedMessageHandler:
    """O'chirilgan signal xabari: pending lar bekor, profitdagi pozitsiyalar breakeven."""

    def __init__(
        self,
        settings: Settings,
        registry: SignalOrderRegistry,
        executor: AiOrderExecutor,
        trading: Any,
        load_context: ContextLoader,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._executor = executor
        self._trading = trading
        self._load_context = load_context

    async def handle(self, chat_id: int, message_ids: list[int]) -> None:
        tickets = self._registry.tickets_for(chat_id, message_ids)
        if not tickets:
            logger.info(
                "Deleted msg(s) %s in chat %s — no linked orders",
                message_ids,
                chat_id,
            )
            return

        magic = self._settings.get_group_magic(chat_id)
        existing, market = await self._load_context(magic, chat_id)
        targets = [item for item in existing if item.order_number in tickets]
        if not targets:
            logger.info(
                "Deleted msg(s) %s in chat %s — linked orders already closed",
                message_ids,
                chat_id,
            )
            self._registry.forget(chat_id, message_ids)
            return

        actions = plan_deleted_signal_actions(targets, market)
        if not actions:
            logger.info(
                "Deleted msg(s) %s in chat %s — %d order(s), nothing to change",
                message_ids,
                chat_id,
                len(targets),
            )
            self._registry.forget(chat_id, message_ids)
            return

        response = AiTradeResponse(
            is_signal=True,
            symbol=targets[0].symbol,
            side="none",
            orders=actions,
            reasoning=f"Signal message(s) {message_ids} deleted by channel",
        )
        logger.info(
            "Deleted signal chat=%s msgs=%s → %d action(s) on %d linked order(s)",
            chat_id,
            message_ids,
            len(actions),
            len(targets),
        )

        results = await self._executor.execute(
            self._trading, response, magic, existing,
        )
        for result in results:
            if result.success:
                logger.info("Deleted-signal action OK: %s", result.message)
            else:
                logger.error("Deleted-signal action failed: %s", result.message)

        self._registry.forget(chat_id, message_ids)
