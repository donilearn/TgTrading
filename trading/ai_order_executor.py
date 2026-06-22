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
from trading.price_normalizer import normalize_price
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
        metaapi: Any,
        response: AiTradeResponse,
        magic: int,
        existing: list[ExistingOrder],
        max_entries: int | None = None,
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
                    metaapi, response, action, magic,
                    existing, entry_index,
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
        total = 0
        for action in response.orders:
            if action.action_type.lower() == "entry":
                total += max(1, action.count_order)
            else:
                total += 1
        return total

    async def _execute_one(
        self,
        metaapi: Any,
        response: AiTradeResponse,
        action: AiOrderAction,
        magic: int,
        existing: list[ExistingOrder],
        index: int,
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
                    metaapi,
                    lambda: self._execute_entry(
                        metaapi.connection, response, action, volume, magic, index,
                    ),
                )
            if action_type == "modify":
                return await run_trade_with_retry(
                    metaapi,
                    lambda: self._execute_modify(metaapi.connection, action, existing),
                )
            if action_type == "close":
                return await run_trade_with_retry(
                    metaapi,
                    lambda: self._execute_close(metaapi.connection, action, existing),
                )
            if action_type == "cancel":
                return await run_trade_with_retry(
                    metaapi,
                    lambda: self._execute_cancel(metaapi.connection, action, existing),
                )

            return TradeResult(
                success=False, skipped=True, symbol=symbol,
                message=f"Unknown type: {action.action_type}",
            )
        except Exception as exc:
            error_msg = format_trade_error(metaapi.api, exc)
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
    ) -> TradeResult:
        symbol = response.symbol or ""
        side = _parse_side(response.side)
        order_type = _parse_order_type(action.order_type)

        spec = await self._spec_cache.get(connection, symbol)
        volume = _round_volume_for_spec(volume, spec)
        entry_price = normalize_price(action.price, spec)
        stop_loss = normalize_price(action.sl, spec)
        take_profit = normalize_price(action.tp, spec)

        if order_type != OrderType.MARKET and entry_price is None:
            raise ValueError(f"{order_type.value} order requires price")

        signal = SignalAnalysis(
            is_signal=True,
            signal_type=SignalType.ENTRY,
            action=side,
            order_type=order_type,
            symbol=symbol,
            stop_loss=stop_loss,
            volume=volume,
        )
        options = build_trade_options(symbol, index, magic, False)
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
    ) -> TradeResult:
        target = _find_order(existing, str(action.count_order))
        if target is None or not target.is_position:
            return TradeResult(
                success=False, skipped=True,
                message=f"Position #{action.count_order} not found",
            )

        await connection.close_position(position_id=target.order_number)
        return TradeResult(
            success=True, symbol=target.symbol, action="close",
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
