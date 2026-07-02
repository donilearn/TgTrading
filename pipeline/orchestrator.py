import asyncio
import contextlib
import logging

from ai.analyzer import SignalAnalyzer
from ai.management_message_detector import message_needs_broker_context
from ai.gemini_client import GeminiClient
from ai.tp_order_count import message_tp_level_count, reference_price_from_market
from config.backend_validation import backend_label
from config.settings import Settings
from models.ai_trade_response import AiTradeResponse
from models.chat_message import ChatMessage
from telegram.client import TelegramService
from telegram.listener import MessageListener
from telegram.message_buffer import MessageBuffer
from trading.auto_breakeven_service import AutoBreakevenService
from trading.ai_order_executor import AiOrderExecutor
from trading.client import create_connection_keeper, create_trading_service
from trading.existing_orders_service import ExistingOrdersService
from trading.order_limit_tracker import OrderLimitTracker
from trading.trading_context_loader import TradingContextLoader
from pipeline.shutdown_handler import ShutdownHandler

logger = logging.getLogger(__name__)

_TELEGRAM_STOP_TIMEOUT = 10.0
_INFLIGHT_DRAIN_TIMEOUT = 15.0


class TradingPipeline:
    def __init__(self, settings: Settings, *, win_mode: bool = False) -> None:
        self._settings = settings
        self._win_mode = win_mode
        self._stopped = False
        self._shutting_down = False
        self._inflight_messages = 0

        self._telegram = TelegramService(settings)
        self._gemini = GeminiClient(settings)
        self._analyzer = SignalAnalyzer(self._gemini, settings)
        self._trading = create_trading_service(settings, win_mode=win_mode)
        self._keeper = create_connection_keeper(
            self._trading,
            win_mode=win_mode,
            settings=settings,
        )
        self._limit_tracker = OrderLimitTracker(
            max_per_channel=settings.max_order_count,
            max_per_message=settings.effective_max_per_message,
        )
        self._executor = AiOrderExecutor(settings)
        self._auto_breakeven = AutoBreakevenService(settings)
        self._existing_orders = ExistingOrdersService()
        self._context_loader = TradingContextLoader(
            self._trading,
            self._existing_orders,
            settings,
            win_mode=win_mode,
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
        *,
        is_edit: bool = False,
    ) -> bool:
        if self._shutting_down or self._stopped:
            logger.info("Ignoring message during shutdown from %s", message.chat_id)
            return False

        self._inflight_messages += 1
        try:
            if self._win_mode:
                return await self._process_message_win(message, context, is_edit=is_edit)
            return await self._process_message_metaapi(message, context, is_edit=is_edit)
        finally:
            self._inflight_messages -= 1

    async def _process_message_win(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
        *,
        is_edit: bool = False,
    ) -> bool:
        try:
            magic = self._settings.get_group_magic(message.chat_id)
            edit_tag = " (edited)" if is_edit else ""
            logger.info(
                "Processing message%s chat=%s magic=%s msg=%s text=%r media=%s",
                edit_tag,
                message.chat_id,
                magic,
                message.message_id,
                (message.text or "")[:120],
                bool(message.media),
            )

            existing, market, _global_count = await self._context_loader.load(
                magic,
                message.chat_id,
                self._settings.group_magic_list,
            )

            if await self._auto_breakeven.apply_on_message(
                self._trading, existing, market,
            ):
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
                is_edit=is_edit,
            )

            return await self._execute_if_actionable(
                message, response, magic, existing, market,
            )

        except Exception:
            logger.exception(
                "Failed to handle message from %s in %s",
                message.sender,
                message.chat_id,
            )
            return False

    async def _process_message_metaapi(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
        *,
        is_edit: bool = False,
    ) -> bool:
        try:
            magic = self._settings.get_group_magic(message.chat_id)
            edit_tag = " (edited)" if is_edit else ""
            logger.info(
                "Processing message%s chat=%s magic=%s msg=%s text=%r media=%s",
                edit_tag,
                message.chat_id,
                magic,
                message.message_id,
                (message.text or "")[:120],
                bool(message.media),
            )

            if message_needs_broker_context(message.text):
                return await self._process_message_metaapi_with_context(
                    message, context, magic, is_edit=is_edit,
                )

            response = await self._analyzer.analyze_message(message, context, is_edit=is_edit)

            if (response.reasoning or "").startswith("Analysis error:"):
                return False

            self._log_analysis(message.chat_id, response, prefix="Analysis (LLM)")

            if not response.is_signal:
                await self._maybe_auto_breakeven_on_active_session(magic, message.chat_id)
                return True

            try:
                existing, market = await self._load_metaapi_context(magic, message.chat_id)
            except Exception as exc:
                logger.error(
                    "MetaAPI session failed for chat=%s — trade skipped: %s",
                    message.chat_id,
                    exc,
                )
                return False

            logger.info(
                "Context loaded chat=%s orders=%d market_symbols=%d",
                message.chat_id,
                len(existing),
                len(market),
            )

            response = self._analyzer.enrich_with_broker_context(
                response, existing, market, message.text,
            )

            return await self._execute_if_actionable(
                message,
                response,
                magic,
                existing,
                market,
                metaapi_session=True,
            )

        except Exception:
            logger.exception(
                "Failed to handle message from %s in %s",
                message.sender,
                message.chat_id,
            )
            return False

    async def _process_message_metaapi_with_context(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
        magic: int,
        *,
        is_edit: bool = False,
    ) -> bool:
        """Profit/BE/partial-close xabarlari — broker snapshot bilan to'liq tahlil."""
        try:
            existing, market = await self._load_metaapi_context(magic, message.chat_id)
        except Exception as exc:
            logger.error(
                "MetaAPI session failed for management msg chat=%s: %s",
                message.chat_id,
                exc,
            )
            return False

        logger.info(
            "Management message chat=%s orders=%d market_symbols=%d",
            message.chat_id,
            len(existing),
            len(market),
        )

        response = await self._analyzer.analyze(
            message, context, existing, market,
            is_edit=is_edit,
        )

        if (response.reasoning or "").startswith("Analysis error:"):
            return False

        return await self._execute_if_actionable(
            message,
            response,
            magic,
            existing,
            market,
            metaapi_session=True,
        )

    async def _load_metaapi_context(
        self,
        magic: int,
        chat_id: int,
    ) -> tuple[list, list]:
        await self._trading.ensure_session(
            self._settings.parsed_allowed_symbols,
        )
        existing, market, _global_count = await self._context_loader.load(
            magic,
            chat_id,
            self._settings.group_magic_list,
        )
        if await self._auto_breakeven.apply_on_message(
            self._trading, existing, market,
        ):
            existing, market, _global_count = await self._context_loader.load(
                magic,
                chat_id,
                self._settings.group_magic_list,
            )
        return existing, market

    async def _maybe_auto_breakeven_on_active_session(
        self,
        magic: int,
        chat_id: int,
    ) -> None:
        """Faol MetaAPI sessiyasi bo'lsa auto-BE — spam xabarda ulanish yo'q."""
        if not getattr(self._trading, "is_connected", False):
            return
        try:
            existing, market, _ = await self._context_loader.load(
                magic,
                chat_id,
                self._settings.group_magic_list,
            )
            await self._auto_breakeven.apply_on_message(
                self._trading, existing, market,
            )
        except Exception as exc:
            logger.debug("Auto-BE on active session skipped chat=%s: %s", chat_id, exc)

    async def _execute_if_actionable(
        self,
        message: ChatMessage,
        response: AiTradeResponse,
        magic: int,
        existing,
        market,
        *,
        metaapi_session: bool = False,
    ) -> bool:
        self._log_analysis(message.chat_id, response)

        if not response.is_actionable:
            if metaapi_session and not self._win_mode:
                self._trading.touch_session()
            return True

        planned_entries = self._executor.count_entry_orders(response)
        existing_group_count = len(existing)

        if planned_entries > 0:
            ref_price = reference_price_from_market(response.symbol, market)
            msg_tp_override = message_tp_level_count(message.text, ref_price)

            allowed, limit_msg, to_place = self._limit_tracker.can_place(
                message.chat_id,
                planned_entries,
                existing_group_count,
                msg_tp_override=msg_tp_override,
            )
            if not allowed:
                logger.info("Trade skipped: %s", limit_msg)
                return True
            if limit_msg:
                logger.info("Trade capped: %s", limit_msg)
        else:
            to_place = None

        results = await self._executor.execute(
            self._trading,
            response,
            magic,
            existing,
            max_entries=to_place,
            channel_name=message.chat_title,
            message_time=message.date,
        )

        entries_placed = 0
        for result in results:
            if result.skipped:
                logger.info("Trade skipped: %s", result.message)
            elif result.success:
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

        if not self._win_mode:
            self._trading.touch_session()

        return True

    @staticmethod
    def _log_analysis(
        chat_id: int,
        response: AiTradeResponse,
        *,
        prefix: str = "Analysis",
    ) -> None:
        for item in response.orders:
            logger.info(
                "%s [%s]: countOrder=%s type=%s price=%s sl=%s tp=%s orderType=%s vol=%s",
                prefix,
                chat_id,
                item.count_order,
                item.action_type,
                item.price,
                item.sl,
                item.tp,
                item.order_type,
                item.volume,
            )
        logger.info(
            "%s [%s]: signal=%s symbol=%s side=%s orders=%d actionable=%s — %s",
            prefix,
            chat_id,
            response.is_signal,
            response.symbol,
            response.side,
            len(response.orders),
            response.is_actionable,
            response.reasoning,
        )

    async def start(self) -> None:
        await self._telegram.start()
        if self._win_mode:
            await self._trading.connect()
        else:
            logger.info(
                "MetaAPI on-demand mode — connect on signal only "
                "(idle_disconnect=%ss, keeper=%s)",
                self._settings.metaapi_idle_disconnect_sec,
                self._settings.metaapi_keeper_enabled,
            )
        if self._win_mode or self._settings.metaapi_keeper_enabled:
            self._keeper.start()
        self._listener.register()

        mode = "LIVE" if self._settings.trading_enabled else "DRY-RUN"
        mode_label = "AGGRESSIVE" if self._settings.aggressive_mode else "NORMAL"
        logger.info(
            "Pipeline started backend=%s trade=%s (%s) — groups: %s, "
            "msg max %d, channel max %d",
            backend_label(self._win_mode),
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
        await self._keeper.stop()
        await self._telegram.stop()
        await self._trading.disconnect()
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