import asyncio
import logging
from typing import Any

from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder
from models.order_type import OrderType
from models.signal import SignalAnalysis, TradeAction
from models.signal_type import SignalType
from models.trade_result import TradeResult
from trading.client_id import build_trade_options
from trading.order_expiration_builder import apply_pending_order_expiration
from trading.error_formatter import format_trade_error
from trading.order_router import OrderRouter
from trading.partial_close_handler import resolve_close_volume
from trading.pending_order_type_resolver import resolve_pending_order_type
from trading.price_normalizer import normalize_price
from trading.sltp_price_resolver import market_entry_price, resolve_default_sltp_prices
from trading.symbol_spec_cache import SymbolSpecCache
from trading.trade_retry import run_trade_with_retry
from trading.volume_normalizer import round_volume

logger = logging.getLogger(__name__)

_ORDER_DELAY_SEC = 0.35


class AiOrderExecutor:
    """Execute AI JSON orders as-is. No strategy logic here."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._router = OrderRouter()
        self._spec_cache = SymbolSpecCache()

    async def execute(
        self,
        trading: Any,
        response: AiTradeResponse,
        magic: int,
        existing: list[ExistingOrder],
        max_entries: int | None = None,
        channel_name: str = "",
        message_time: str | None = None,
    ) -> list[TradeResult]:
        if not response.is_actionable:
            return [TradeResult(
                success=False, skipped=True,
                message=f"Not actionable: {response.reasoning}",
            )]

        results: list[TradeResult] = []
        entry_index = 0
        entries_placed = 0
        planned_entries = self.count_planned_orders(response)

        for action in response.orders:
            action_type = action.action_type.lower()
            repeat = action.count_order if action_type == "entry" else 1

            for _ in range(max(1, repeat)):
                if action_type == "entry" and max_entries is not None:
                    if entries_placed >= max_entries:
                        break
                result = await self._execute_one(
                    trading, response, action, magic,
                    existing, entry_index,
                    channel_name, message_time,
                )
                results.append(result)
                if action_type == "entry":
                    entry_index += 1
                    entries_placed += 1
                if len(results) < planned_entries:
                    await asyncio.sleep(_ORDER_DELAY_SEC)

            if action_type == "entry" and max_entries is not None:
                if entries_placed >= max_entries:
                    break

        return results

    def count_planned_orders(self, response: AiTradeResponse) -> int:
        return self.count_entry_orders(response) + self.count_management_orders(response)

    def count_entry_orders(self, response: AiTradeResponse) -> int:
        total = 0
        for action in response.orders:
            if action.action_type.lower() == "entry":
                total += max(1, action.count_order)
        return total

    def count_management_orders(self, response: AiTradeResponse) -> int:
        return sum(
            1 for action in response.orders
            if action.action_type.lower() != "entry"
        )

    async def _execute_one(
        self,
        trading: Any,
        response: AiTradeResponse,
        action: AiOrderAction,
        magic: int,
        existing: list[ExistingOrder],
        index: int,
        channel_name: str = "",
        message_time: str | None = None,
    ) -> TradeResult:
        symbol = response.symbol or ""
        action_type = action.action_type.lower()
        volume = self._normalize_volume(action.volume)

        if not self._settings.trading_enabled:
            logger.warning(
                "DRY-RUN: %s %s countOrder=%s price=%s sl=%s tp=%s orderType=%s vol=%s",
                action_type, symbol, action.count_order,
                action.price, action.sl, action.tp, action.order_type, volume,
            )
            return TradeResult(
                success=True, skipped=True, symbol=symbol,
                action=response.side, volume=volume,
                message="Trading disabled — dry-run",
            )

        try:
            if action_type == "entry":
                return await run_trade_with_retry(
                    trading,
                    lambda conn: self._execute_entry(
                        conn, response, action, volume, magic, index,
                        channel_name, message_time,
                    ),
                )
            if action_type == "modify":
                return await run_trade_with_retry(
                    trading,
                    lambda conn: self._execute_modify(conn, action, existing),
                )
            if action_type == "close":
                return await run_trade_with_retry(
                    trading,
                    lambda conn: self._execute_close(
                        conn, action, existing, channel_name, message_time,
                    ),
                )
            if action_type == "cancel":
                return await run_trade_with_retry(
                    trading,
                    lambda conn: self._execute_cancel(conn, action, existing),
                )

            return TradeResult(
                success=False, skipped=True, symbol=symbol,
                message=f"Unknown type: {action.action_type}",
            )
        except Exception as exc:
            error_msg = format_trade_error(trading.api, exc)
            logger.error(
                "Execute failed: %s | %s %s price=%s vol=%s",
                error_msg, action.action_type, action.order_type,
                action.price, volume,
            )
            return TradeResult(
                success=False, symbol=symbol,
                action=response.side, volume=volume, message=error_msg,
            )

    async def _execute_entry(
        self,
        connection: Any,
        response: AiTradeResponse,
        action: AiOrderAction,
        volume: float,
        magic: int,
        index: int,
        channel_name: str = "",
        message_time: str | None = None,
    ) -> TradeResult:
        symbol = response.symbol or ""
        side = _parse_side(response.side)
        order_type = _parse_order_type(action.order_type)

        spec = await self._spec_cache.get(connection, symbol)
        volume = _round_volume_for_spec(volume, spec)
        entry_price = normalize_price(action.price, spec)
        stop_loss = normalize_price(action.sl, spec)
        take_profit = normalize_price(action.tp, spec)
        stop_loss, take_profit = await self._resolve_entry_sltp(
            connection,
            symbol,
            response.side,
            entry_price,
            spec,
            stop_loss,
            take_profit,
        )

        if order_type != OrderType.MARKET and entry_price is None:
            raise ValueError(f"{order_type.value} order requires price")

        if order_type != OrderType.MARKET and entry_price is not None:
            order_type = await self._resolve_pending_order_type(
                connection, symbol, response.side, entry_price, order_type,
            )

        signal = SignalAnalysis(
            is_signal=True,
            signal_type=SignalType.ENTRY,
            action=side,
            order_type=order_type,
            symbol=symbol,
            stop_loss=stop_loss,
            volume=volume,
        )
        options = build_trade_options(magic, channel_name, message_time)
        options = apply_pending_order_expiration(
            options,
            order_type,
            action.expiration_minutes,
            self._settings.orders_expiration_minutes,
        )

        result = await self._router.place_order(
            connection, signal, volume, entry_price,
            stop_loss, take_profit, None, None, options,
            order_type=order_type,
        )
        return TradeResult(
            success=True, symbol=symbol, action=side.value,
            volume=volume, message=result.get("stringCode", "OK"),
        )

    async def _execute_modify(
        self,
        connection: Any,
        action: AiOrderAction,
        existing: list[ExistingOrder],
    ) -> TradeResult:
        target = _find_order(existing, str(action.count_order))
        if target is None:
            return TradeResult(
                success=False, skipped=True,
                message=f"Order #{action.count_order} not found",
            )

        spec = await self._spec_cache.get(connection, target.symbol)
        stop_loss = normalize_price(action.sl, spec)
        take_profit = normalize_price(action.tp, spec)
        open_price = normalize_price(
            action.price if action.price is not None else target.open_price,
            spec,
        )

        if target.is_position:
            kwargs = {"position_id": target.order_number}
            if stop_loss is not None:
                kwargs["stop_loss"] = stop_loss
            if take_profit is not None:
                kwargs["take_profit"] = take_profit
            await connection.modify_position(**kwargs)
        else:
            kwargs = {"order_id": target.order_number, "open_price": open_price}
            if stop_loss is not None:
                kwargs["stop_loss"] = stop_loss
            if take_profit is not None:
                kwargs["take_profit"] = take_profit
            await connection.modify_order(**kwargs)

        return TradeResult(
            success=True, symbol=target.symbol, action="modify",
            message=f"Modified #{action.count_order}",
        )

    async def _execute_close(
        self,
        connection: Any,
        action: AiOrderAction,
        existing: list[ExistingOrder],
        channel_name: str = "",
        message_time: str | None = None,
    ) -> TradeResult:
        target = _find_order(existing, str(action.count_order))
        if target is None:
            return TradeResult(
                success=False, skipped=True,
                message=f"Order #{action.count_order} not found",
            )

        # Pending limit/stop → close = cancel (AI ko'pincha type=close yuboradi)
        if not target.is_position:
            if action.volume is not None:
                return TradeResult(
                    success=False,
                    skipped=True,
                    symbol=target.symbol,
                    action="cancel",
                    message=(
                        f"Pending order #{action.count_order} — "
                        "qisman yopish mumkin emas, faqat cancel"
                    ),
                )
            await connection.cancel_order(order_id=target.order_number)
            return TradeResult(
                success=True, symbol=target.symbol, action="cancel",
                message=f"Cancelled pending #{action.count_order}",
            )

        comment = build_trade_options(0, channel_name, message_time)["comment"]

        close_mode, close_volume = resolve_close_volume(
            action.volume,
            target,
            self._settings.min_volume,
        )

        if close_mode == "too_small":
            return TradeResult(
                success=False,
                skipped=True,
                symbol=target.symbol,
                action="close",
                message=(
                    f"Partial close #{action.count_order} too small "
                    f"(vol={action.volume}, min={self._settings.min_volume})"
                ),
            )

        if close_mode == "partial" and close_volume is not None:
            spec = await self._spec_cache.get(connection, target.symbol)
            close_volume = _round_volume_for_spec(close_volume, spec)
            await connection.close_position_partially(
                position_id=target.order_number,
                volume=close_volume,
                comment=comment,
            )
            return TradeResult(
                success=True,
                symbol=target.symbol,
                action="close",
                volume=close_volume,
                message=f"Partially closed #{action.count_order} vol={close_volume}",
            )

        await connection.close_position(
            position_id=target.order_number,
            comment=comment,
        )
        return TradeResult(
            success=True, symbol=target.symbol, action="close",
            volume=target.volume,
            message=f"Closed #{action.count_order}",
        )

    async def _execute_cancel(
        self,
        connection: Any,
        action: AiOrderAction,
        existing: list[ExistingOrder],
    ) -> TradeResult:
        target = _find_order(existing, str(action.count_order))
        if target is None or target.is_position:
            return TradeResult(
                success=False, skipped=True,
                message=f"Pending order #{action.count_order} not found",
            )

        await connection.cancel_order(order_id=target.order_number)
        return TradeResult(
            success=True, symbol=target.symbol, action="cancel",
            message=f"Cancelled #{action.count_order}",
        )

    def _normalize_volume(self, volume: float | None) -> float:
        raw = volume or self._settings.default_volume
        clamped = max(self._settings.min_volume, min(raw, self._settings.max_volume))
        return round_volume(clamped)

    async def _resolve_pending_order_type(
        self,
        connection: Any,
        symbol: str,
        side: str,
        entry_price: float,
        requested: OrderType,
    ) -> OrderType:
        if requested not in (OrderType.LIMIT, OrderType.STOP):
            return requested

        quote = await self._spec_cache.get_price(connection, symbol)
        bid = _to_float(quote.get("bid"))
        ask = _to_float(quote.get("ask"))
        resolved = resolve_pending_order_type(side, entry_price, bid, ask)
        order_type = _parse_order_type(resolved)

        if order_type != requested:
            logger.info(
                "Pending type adjusted %s %s @%.3f bid=%s ask=%s → %s (was %s)",
                side,
                symbol,
                entry_price,
                bid,
                ask,
                order_type.value,
                requested.value,
            )
        return order_type

    async def _resolve_entry_sltp(
        self,
        connection: Any,
        symbol: str,
        side: str,
        entry_price: float | None,
        spec: dict,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> tuple[float | None, float | None]:
        if stop_loss is not None and take_profit is not None:
            return stop_loss, take_profit
        if self._settings.default_sl_pips <= 0 and self._settings.default_tp_pips <= 0:
            return stop_loss, take_profit

        price_base = entry_price
        if price_base is None:
            quote = await self._spec_cache.get_price(connection, symbol)
            price_base = market_entry_price(side, quote)

        return resolve_default_sltp_prices(
            side=side,
            entry_price=price_base,
            spec=spec,
            default_sl_pips=self._settings.default_sl_pips,
            default_tp_pips=self._settings.default_tp_pips,
            existing_sl=stop_loss,
            existing_tp=take_profit,
        )


def _round_volume_for_spec(volume: float, spec: dict) -> float:
    step = _to_float(spec.get("volumeStep")) or _to_float(spec.get("minVolume"))
    if not step or step <= 0:
        return volume
    steps = max(1, round(volume / step))
    return round_volume(round(steps * step, 10))


def _find_order(existing: list[ExistingOrder], order_number: str) -> ExistingOrder | None:
    for item in existing:
        if item.order_number == order_number:
            return item
    return None


def _parse_side(side: str) -> TradeAction:
    if side.lower() == "buy":
        return TradeAction.BUY
    if side.lower() == "sell":
        return TradeAction.SELL
    return TradeAction.NONE


def _parse_order_type(raw: str) -> OrderType:
    mapping = {
        "market": OrderType.MARKET,
        "limit": OrderType.LIMIT,
        "stop": OrderType.STOP,
    }
    return mapping.get(raw.lower(), OrderType.LIMIT)


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
