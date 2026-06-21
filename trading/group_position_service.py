import logging
from typing import Any

from models.modify_scope import ModifyScope
from models.signal import SignalAnalysis
from trading.magic_matcher import matches_magic
from trading.stop_options_builder import build_stop_options
from trading.trade_target_filter import filter_by_targets

logger = logging.getLogger(__name__)


class GroupPositionService:
    """Manage positions and orders scoped to a group's magic number."""

    async def get_positions(
        self,
        connection: Any,
        magic: int,
        symbol: str | None = None,
    ) -> list[dict]:
        positions = await connection.get_positions()
        matched = [
            pos for pos in positions
            if matches_magic(pos, magic)
            and (not symbol or pos.get("symbol") == symbol)
        ]

        if not matched and positions:
            logger.debug(
                "No positions for magic=%s symbol=%s. Available: %s",
                magic,
                symbol or "any",
                [
                    (p.get("id"), p.get("symbol"), p.get("magic"))
                    for p in positions
                ],
            )

        return matched

    async def get_orders(
        self,
        connection: Any,
        magic: int,
        symbol: str | None = None,
    ) -> list[dict]:
        orders = await connection.get_orders()
        return [
            order for order in orders
            if matches_magic(order, magic)
            and (not symbol or order.get("symbol") == symbol)
        ]

    async def modify_group_positions(
        self,
        connection: Any,
        magic: int,
        signal: SignalAnalysis,
    ) -> list[dict]:
        symbol = signal.symbol
        if not symbol:
            logger.warning("UPDATE requires symbol (magic=%s)", magic)
            return []

        positions = filter_by_targets(
            await self.get_positions(connection, magic, symbol),
            signal.target_position_ids,
        )
        orders = filter_by_targets(
            await self.get_orders(connection, magic, symbol),
            signal.target_order_ids,
        )

        if signal.modify_scope == ModifyScope.POSITIONS:
            orders = []
        elif signal.modify_scope == ModifyScope.ORDERS:
            positions = []

        shared_stop_loss = build_stop_options(signal.stop_loss, signal.sl_pips)
        shared_take_profit = build_stop_options(
            signal.primary_take_profit,
            signal.tp_pips,
        )

        if not signal.breakeven_sl and shared_stop_loss is None and shared_take_profit is None:
            return []

        stop_price_base = None
        if signal.sl_pips is not None or signal.tp_pips is not None:
            stop_price_base = "CURRENT_PRICE"

        if not positions and not orders:
            all_positions = await connection.get_positions()
            all_orders = await connection.get_orders()
            logger.warning(
                "Nothing to update for magic=%s symbol=%s scope=%s targets=%s/%s. "
                "Positions: %s | Pending orders: %s",
                magic,
                symbol,
                signal.modify_scope.value,
                signal.target_position_ids,
                signal.target_order_ids,
                [(p.get("symbol"), p.get("magic"), p.get("id")) for p in all_positions],
                [(o.get("symbol"), o.get("magic"), o.get("id")) for o in all_orders],
            )
            return []

        results = []

        for pos in positions:
            stop_loss = _resolve_stop_loss(signal, pos, shared_stop_loss)
            take_profit = shared_take_profit

            if stop_loss is None and take_profit is None:
                continue

            modify_kwargs = {"position_id": str(pos["id"])}
            if stop_loss is not None:
                modify_kwargs["stop_loss"] = stop_loss
            if take_profit is not None:
                modify_kwargs["take_profit"] = take_profit
            if stop_price_base is not None:
                modify_kwargs["stop_price_base"] = stop_price_base

            result = await connection.modify_position(**modify_kwargs)
            results.append(result)
            logger.info(
                "Modified position %s (%s) magic=%s SL=%s TP=%s",
                pos["id"],
                pos.get("symbol"),
                magic,
                stop_loss,
                take_profit,
            )

        for order in orders:
            open_price = order.get("openPrice")
            if open_price is None:
                continue

            stop_loss = _resolve_stop_loss(signal, order, shared_stop_loss)
            take_profit = shared_take_profit

            if stop_loss is None and take_profit is None:
                continue

            modify_options = None
            if stop_price_base is not None:
                modify_options = {"stopPriceBase": stop_price_base}

            result = await connection.modify_order(
                order_id=str(order["id"]),
                open_price=open_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                options=modify_options,
            )
            results.append(result)
            logger.info(
                "Modified pending order %s (%s) magic=%s SL=%s TP=%s",
                order["id"],
                order.get("symbol"),
                magic,
                stop_loss,
                take_profit,
            )

        return results

    async def close_group_positions(
        self,
        connection: Any,
        magic: int,
        signal: SignalAnalysis,
    ) -> list[dict]:
        symbol = signal.symbol
        positions = filter_by_targets(
            await self.get_positions(connection, magic, symbol),
            signal.target_position_ids,
        )
        results = []

        for pos in positions:
            result = await connection.close_position(position_id=str(pos["id"]))
            results.append(result)
            logger.info(
                "Closed position %s (%s) magic=%s",
                pos["id"],
                pos.get("symbol"),
                pos.get("magic"),
            )

        return results

    async def cancel_group_orders(
        self,
        connection: Any,
        magic: int,
        signal: SignalAnalysis,
    ) -> list[dict]:
        symbol = signal.symbol
        orders = filter_by_targets(
            await self.get_orders(connection, magic, symbol),
            signal.target_order_ids,
        )
        results = []

        for order in orders:
            result = await connection.cancel_order(order_id=str(order["id"]))
            results.append(result)
            logger.info(
                "Cancelled order %s (%s) magic=%s",
                order["id"],
                order.get("symbol"),
                order.get("magic"),
            )

        return results


def _resolve_stop_loss(
    signal: SignalAnalysis,
    entity: dict,
    shared_stop_loss: Any,
) -> Any:
    if signal.breakeven_sl:
        open_price = entity.get("openPrice")
        if open_price is not None:
            return float(open_price)
        return None
    return shared_stop_loss
