import logging

from config.settings import Settings
from models.order_plan import OrderPlan
from models.signal import SignalAnalysis
from models.signal_type import SignalType
from models.trade_result import TradeResult
from trading.client import MetaApiService
from trading.client_id import build_trade_options
from trading.order_expiration_builder import apply_pending_order_expiration
from trading.error_formatter import format_trade_error
from trading.group_position_service import GroupPositionService
from trading.order_limit_tracker import OrderLimitTracker
from trading.order_router import OrderRouter
from trading.symbol_validator import resolve_env_symbol
from trading.zone_order_planner import ZoneOrderPlanner

logger = logging.getLogger(__name__)


class TradeExecutor:
    def __init__(
        self,
        metaapi_service: MetaApiService,
        settings: Settings,
        limit_tracker: OrderLimitTracker,
    ) -> None:
        self._metaapi = metaapi_service
        self._settings = settings
        self._limit_tracker = limit_tracker
        self._router = OrderRouter()
        self._positions = GroupPositionService()
        self._order_planner = ZoneOrderPlanner(settings)

    async def execute(
        self,
        signal: SignalAnalysis,
        chat_id: int,
    ) -> list[TradeResult]:
        if not signal.is_actionable:
            return [TradeResult(
                success=False,
                skipped=True,
                message=f"Signal not actionable: {signal.reasoning}",
            )]

        magic = self._settings.get_group_magic(chat_id)

        if signal.symbol:
            resolved = resolve_env_symbol(
                signal.symbol,
                self._settings.parsed_allowed_symbols,
            )
            if not resolved:
                return [TradeResult(
                    success=False,
                    skipped=True,
                    symbol=signal.symbol,
                    message=f"Symbol {signal.symbol} not in allowed list",
                )]
            signal.symbol = resolved
        elif signal.signal_type in (
            SignalType.ENTRY,
            SignalType.RE_ENTRY,
            SignalType.CLOSE,
        ):
            return [TradeResult(
                success=False,
                skipped=True,
                message="Symbol required for this signal type",
            )]

        if signal.signal_type == SignalType.UPDATE:
            return await self._execute_update(signal, magic)

        if signal.signal_type == SignalType.CANCEL:
            return await self._execute_cancel(signal, magic)

        if signal.signal_type == SignalType.CLOSE:
            return await self._execute_close(signal, chat_id, magic)

        return await self._execute_entry(signal, chat_id, magic)

    async def _execute_update(
        self,
        signal: SignalAnalysis,
        magic: int,
    ) -> list[TradeResult]:
        symbol = signal.symbol or ""

        if not self._settings.trading_enabled:
            logger.warning(
                "DRY-RUN: would UPDATE magic=%s symbol=%s scope=%s "
                "targets pos=%s ord=%s breakeven=%s SL=%s TP=%s sl_pips=%s tp_pips=%s",
                magic, symbol or "all", signal.modify_scope.value,
                signal.target_position_ids, signal.target_order_ids,
                signal.breakeven_sl, signal.stop_loss,
                signal.primary_take_profit, signal.sl_pips, signal.tp_pips,
            )
            return [TradeResult(
                success=True, skipped=True, symbol=symbol, action="update",
                message="Trading disabled — dry-run update",
            )]

        try:
            results = await self._positions.modify_group_positions(
                self._metaapi.connection, magic, signal,
            )
            if not results:
                return [TradeResult(
                    success=False, skipped=True, symbol=symbol, action="update",
                    message=f"No positions/orders for magic={magic} symbol={symbol}",
                )]
            return [TradeResult(
                success=True, symbol=symbol, action="update",
                message=f"Updated {len(results)} position/order(s)",
            )]
        except Exception as exc:
            error_msg = format_trade_error(self._metaapi.api, exc)
            return [TradeResult(
                success=False, symbol=symbol, action="update", message=error_msg,
            )]

    async def _execute_cancel(
        self,
        signal: SignalAnalysis,
        magic: int,
    ) -> list[TradeResult]:
        symbol = signal.symbol or ""

        if not self._settings.trading_enabled:
            logger.warning("DRY-RUN: would CANCEL orders magic=%s", magic)
            return [TradeResult(
                success=True, skipped=True, symbol=symbol, action="cancel",
                message="Trading disabled — dry-run cancel",
            )]

        try:
            results = await self._positions.cancel_group_orders(
                self._metaapi.connection, magic, signal,
            )
            if not results:
                return [TradeResult(
                    success=False, skipped=True, symbol=symbol, action="cancel",
                    message=f"No pending orders for magic={magic}",
                )]
            return [TradeResult(
                success=True, symbol=symbol, action="cancel",
                message=f"Cancelled {len(results)} order(s)",
            )]
        except Exception as exc:
            error_msg = format_trade_error(self._metaapi.api, exc)
            return [TradeResult(
                success=False, symbol=symbol, action="cancel", message=error_msg,
            )]

    async def _execute_close(
        self,
        signal: SignalAnalysis,
        chat_id: int,
        magic: int,
    ) -> list[TradeResult]:
        allowed, limit_msg, _ = self._limit_tracker.can_place(chat_id, 1, 0)
        if not allowed:
            return [TradeResult(success=False, skipped=True, message=limit_msg)]

        result = await self._execute_close_order(signal, magic)
        if result.success and not result.skipped:
            self._limit_tracker.record(chat_id, 1)
        return [result]

    async def _execute_close_order(
        self,
        signal: SignalAnalysis,
        magic: int,
    ) -> TradeResult:
        symbol = signal.symbol or ""

        if not self._settings.trading_enabled:
            logger.warning(
                "DRY-RUN: would CLOSE positions magic=%s symbol=%s",
                magic, symbol,
            )
            return TradeResult(
                success=True, skipped=True, symbol=symbol,
                action="close", message="Trading disabled — dry-run close",
            )

        try:
            results = await self._positions.close_group_positions(
                self._metaapi.connection, magic, signal,
            )
            if not results:
                return TradeResult(
                    success=False, skipped=True, symbol=symbol,
                    action="close", message=f"No positions for magic={magic}",
                )
            return TradeResult(
                success=True, symbol=symbol, action="close",
                message=f"Closed {len(results)} position(s)",
            )
        except Exception as exc:
            error_msg = format_trade_error(self._metaapi.api, exc)
            return TradeResult(
                success=False, symbol=symbol, action="close", message=error_msg,
            )

    async def _execute_entry(
        self,
        signal: SignalAnalysis,
        chat_id: int,
        magic: int,
        existing_channel_count: int,
    ) -> list[TradeResult]:
        orders = self._order_planner.build(signal)

        allowed, limit_msg, _ = self._limit_tracker.can_place(
            chat_id, len(orders), existing_channel_count,
        )
        if not allowed:
            return [TradeResult(success=False, skipped=True, message=limit_msg)]

        results: list[TradeResult] = []
        success_count = 0

        for i, plan in enumerate(orders):
            result = await self._place_single_order(signal, plan, index=i, magic=magic)
            results.append(result)
            if result.success and not result.skipped:
                success_count += 1

        if success_count:
            self._limit_tracker.record(chat_id, success_count)

        return results

    async def _place_single_order(
        self,
        signal: SignalAnalysis,
        plan: OrderPlan,
        index: int,
        magic: int,
    ) -> TradeResult:
        volume = plan.volume
        entry_price = plan.entry_price
        take_profit = plan.take_profit
        action = signal.action.value
        symbol = signal.symbol or ""

        order_type = plan.order_type or signal.order_type

        order_label = (
            f"{order_type.value} {action} {symbol} "
            f"vol={volume} entry={entry_price} "
            f"SL={plan.stop_loss or plan.sl_pips} TP={take_profit or plan.tp_pips}"
        )

        if not self._settings.trading_enabled:
            logger.warning("DRY-RUN: %s", order_label)
            return TradeResult(
                success=True, skipped=True, symbol=symbol,
                action=action, volume=volume,
                message=f"Dry-run: {order_label}",
            )

        try:
            options = build_trade_options(
                symbol, index, magic, signal.is_re_entry,
            )
            options = apply_pending_order_expiration(
                options,
                order_type,
                None,
                self._settings.orders_expiration_minutes,
            )

            result = await self._router.place_order(
                self._metaapi.connection,
                signal,
                volume,
                entry_price,
                plan.stop_loss,
                take_profit,
                plan.sl_pips,
                plan.tp_pips,
                options,
                order_type=order_type,
            )

            logger.info("Order placed: %s — %s", order_label, result.get("stringCode", "OK"))
            return TradeResult(
                success=True,
                string_code=result.get("stringCode", ""),
                numeric_code=result.get("numericCode"),
                symbol=symbol, action=action, volume=volume,
                message="Order placed successfully",
            )

        except Exception as exc:
            error_msg = format_trade_error(self._metaapi.api, exc)
            logger.error("Order failed: %s — %s", order_label, error_msg)
            return TradeResult(
                success=False, symbol=symbol, action=action,
                volume=volume, message=error_msg,
            )