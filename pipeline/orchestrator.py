import asyncio
import contextlib
import logging

from ai.analyzer import SignalAnalyzer
from ai.client import GeminiClient
from config.settings import Settings
from models.chat_message import ChatMessage
from telegram.client import TelegramService
from telegram.listener import MessageListener
from telegram.message_buffer import MessageBuffer
from trading.ai_order_executor import AiOrderExecutor
from trading.client import MetaApiService
from trading.existing_orders_service import ExistingOrdersService
from trading.market_context_service import MarketContextService
from trading.order_limit_tracker import OrderLimitTracker
from pipeline.shutdown_handler import ShutdownHandler

logger = logging.getLogger(__name__)

_TELEGRAM_STOP_TIMEOUT = 10.0


class TradingPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stopped = False

        self._telegram = TelegramService(settings)
        self._gemini = GeminiClient(settings)
        self._analyzer = SignalAnalyzer(self._gemini, settings)
        self._metaapi = MetaApiService(settings)
        self._limit_tracker = OrderLimitTracker(
            max_orders=settings.effective_max_order_count,
            max_per_group=settings.effective_max_order_per_group,
        )
        self._executor = AiOrderExecutor(settings)
        self._existing_orders = ExistingOrdersService()
        self._market_context = MarketContextService(settings)
        self._message_buffer = MessageBuffer(
            max_size=settings.context_message_count,
        )

        self._listener = MessageListener(
            telegram_service=self._telegram,
            group_ids=settings.parsed_group_ids,
            message_buffer=self._message_buffer,
            on_message=self._handle_message,
        )

    async def _handle_message(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
    ) -> None:
        try:
            magic = self._settings.get_group_magic(message.chat_id)
            existing = await self._existing_orders.fetch(
                self._metaapi.connection, magic,
            )
            market = await self._market_context.build(
                self._metaapi.connection, existing,
            )
            response = await self._analyzer.analyze(
                message, context, existing, market,
            )

            for item in response.orders:
                logger.info(
                    "Analysis [%s]: countOrder=%s type=%s price=%s sl=%s tp=%s orderType=%s vol=%s",
                    message.chat_id,
                    item.count_order,
                    item.action_type,
                    item.price,
                    item.sl,
                    item.tp,
                    item.order_type,
                    item.volume,
                )
            logger.info(
                "Analysis [%s]: signal=%s symbol=%s side=%s orders=%d actionable=%s — %s",
                message.chat_id,
                response.is_signal,
                response.symbol,
                response.side,
                len(response.orders),
                response.is_actionable,
                response.reasoning,
            )

            if not response.is_actionable:
                return

            planned = self._executor.count_planned_orders(response)
            existing_count = len(existing)
            allowed, limit_msg, to_place = self._limit_tracker.can_place(
                message.chat_id, planned, existing_count,
            )
            if not allowed:
                logger.info("Trade skipped: %s", limit_msg)
                return
            if limit_msg:
                logger.info("Trade capped: %s", limit_msg)

            results = await self._executor.execute(
                self._metaapi,
                response,
                magic,
                existing,
                max_entries=to_place,
            )

            success_count = 0
            for result in results:
                if result.skipped:
                    logger.info("Trade skipped: %s", result.message)
                elif result.success:
                    success_count += 1
                    logger.info(
                        "Trade OK: %s %s vol=%.2f — %s",
                        result.action,
                        result.symbol,
                        result.volume or 0,
                        result.message,
                    )
                else:
                    logger.error("Trade failed: %s", result.message)

            if success_count:
                self._limit_tracker.record(message.chat_id, success_count)

        except Exception:
            logger.exception(
                "Failed to handle message from %s in %s",
                message.sender,
                message.chat_id,
            )

    async def start(self) -> None:
        await self._telegram.start()
        await self._metaapi.connect()
        self._listener.register()

        mode = "LIVE" if self._settings.trading_enabled else "DRY-RUN"
        aggressive = "ON (2x limits)" if self._settings.aggressive_mode else "OFF"
        logger.info(
            "Pipeline started in %s mode — groups: %s, "
            "max %d/group, max %d total, aggressive=%s",
            mode,
            self._settings.parsed_group_ids,
            self._settings.effective_max_order_per_group,
            self._settings.effective_max_order_count,
            aggressive,
        )
        for chat_id, magic in self._settings.group_magic_by_id.items():
            logger.info("  Group %s → magic %s", chat_id, magic)

    async def run(self) -> None:
        await self.start()
        try:
            await self._run_until_shutdown()
        finally:
            await self.stop()

    async def _run_until_shutdown(self) -> None:
        shutdown = ShutdownHandler()
        shutdown.register()

        run_task = asyncio.create_task(
            self._telegram.client.run_until_disconnected(),
            name="telegram-listener",
        )
        shutdown_task = asyncio.create_task(
            shutdown.wait(),
            name="shutdown-wait",
        )

        done, _pending = await asyncio.wait(
            [run_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if shutdown_task in done:
            logger.info("Graceful shutdown started")
            await self._telegram.stop()

            if not run_task.done():
                with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                    await asyncio.wait_for(run_task, timeout=_TELEGRAM_STOP_TIMEOUT)
                if not run_task.done():
                    run_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await run_task
            return

        exc = run_task.exception()
        if exc is not None:
            raise exc

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True

        await self._metaapi.disconnect()
        await self._telegram.stop()
