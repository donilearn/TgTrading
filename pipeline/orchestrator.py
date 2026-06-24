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
from trading.metaapi_connection_keeper import MetaApiConnectionKeeper
from trading.order_limit_tracker import OrderLimitTracker
from trading.trading_context_loader import TradingContextLoader
from pipeline.shutdown_handler import ShutdownHandler

logger = logging.getLogger(__name__)

_TELEGRAM_STOP_TIMEOUT = 10.0
_INFLIGHT_DRAIN_TIMEOUT = 15.0


class TradingPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stopped = False
        self._shutting_down = False
        self._inflight_messages = 0

        self._telegram = TelegramService(settings)
        self._gemini = GeminiClient(settings)
        self._analyzer = SignalAnalyzer(self._gemini, settings)
        self._metaapi = MetaApiService(settings)
        self._metaapi_keeper = MetaApiConnectionKeeper(self._metaapi)
        self._metaapi.attach_keeper(self._metaapi_keeper)
        self._limit_tracker = OrderLimitTracker(
            max_per_channel=settings.max_order_count,
            max_per_message=settings.effective_max_per_message,
        )
        self._executor = AiOrderExecutor(settings)
        self._existing_orders = ExistingOrdersService()
        self._context_loader = TradingContextLoader(
            self._metaapi,
            self._existing_orders,
            settings,
        )
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
        if self._shutting_down or self._stopped:
            logger.info("Ignoring message during shutdown from %s", message.chat_id)
            return

        self._inflight_messages += 1
        try:
            await self._process_message(message, context)
        finally:
            self._inflight_messages -= 1

    async def _process_message(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
    ) -> None:
        try:
            magic = self._settings.get_group_magic(message.chat_id)
            logger.info(
                "Processing message chat=%s magic=%s text=%r media=%s",
                message.chat_id,
                magic,
                (message.text or "")[:120],
                bool(message.media),
            )

            existing, market, _global_count = await self._context_loader.load(
                magic,
                message.chat_id,
                self._settings.group_magic_list,
            )
            logger.info(
                "Context loaded chat=%s orders=%d market_symbols=%d",
                message.chat_id,
                len(existing),
                len(market),
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

            planned_entries = self._executor.count_entry_orders(response)
            existing_group_count = len(existing)

            if planned_entries > 0:
                allowed, limit_msg, to_place = self._limit_tracker.can_place(
                    message.chat_id,
                    planned_entries,
                    existing_group_count,
                )
                if not allowed:
                    logger.info("Trade skipped: %s", limit_msg)
                    return
                if limit_msg:
                    logger.info("Trade capped: %s", limit_msg)
            else:
                to_place = None
                limit_msg = ""

            results = await self._executor.execute(
                self._metaapi,
                response,
                magic,
                existing,
                max_entries=to_place,
            )

            success_count = 0
            entries_placed = 0
            for result in results:
                if result.skipped:
                    logger.info("Trade skipped: %s", result.message)
                elif result.success:
                    success_count += 1
                    if result.action not in ("close", "cancel", "modify"):
                        entries_placed += 1
                    logger.info(
                        "Trade OK: %s %s vol=%.2f — %s",
                        result.action,
                        result.symbol,
                        result.volume or 0,
                        result.message,
                    )
                else:
                    logger.error("Trade failed: %s", result.message)

            if entries_placed:
                self._limit_tracker.record(message.chat_id, entries_placed)

        except Exception:
            logger.exception(
                "Failed to handle message from %s in %s",
                message.sender,
                message.chat_id,
            )

    async def start(self) -> None:
        await self._telegram.start()
        await self._metaapi.connect()
        await self._metaapi.subscribe_market_data(
            self._settings.parsed_allowed_symbols,
        )
        self._metaapi_keeper.start()
        self._listener.register()

        mode = "LIVE" if self._settings.trading_enabled else "DRY-RUN"
        mode_label = "AGGRESSIVE" if self._settings.aggressive_mode else "NORMAL"
        logger.info(
            "Pipeline started in %s mode (%s) — groups: %s, "
            "msg max %d, channel max %d",
            mode,
            mode_label,
            self._settings.parsed_group_ids,
            self._settings.effective_max_per_message,
            self._settings.max_order_count,
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
            self._shutting_down = True
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
        self._shutting_down = True

        await self._wait_for_inflight_handlers()
        await self._metaapi_keeper.stop()
        await self._telegram.stop()
        await self._metaapi.disconnect()
        logger.info("Pipeline stopped")

    async def _wait_for_inflight_handlers(self) -> None:
        if self._inflight_messages <= 0:
            return

        logger.info(
            "Waiting for %d in-flight message handler(s)...",
            self._inflight_messages,
        )
        deadline = asyncio.get_running_loop().time() + _INFLIGHT_DRAIN_TIMEOUT
        while self._inflight_messages > 0:
            if asyncio.get_running_loop().time() >= deadline:
                logger.warning(
                    "Shutdown timeout: %d handler(s) still running",
                    self._inflight_messages,
                )
                return
            await asyncio.sleep(0.1)
