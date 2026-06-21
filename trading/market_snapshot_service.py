import logging
from typing import Any

from models.order_snapshot import OrderSnapshot
from models.position_snapshot import PositionSnapshot
from models.symbol_quote import SymbolQuote
from models.trading_snapshot import TradingSnapshot
from trading.magic_matcher import matches_magic

logger = logging.getLogger(__name__)


class MarketSnapshotService:
    """Fetch open positions, pending orders, and quotes for AI context."""

    async def build(
        self,
        connection: Any,
        magic: int,
        allowed_symbols: list[str],
    ) -> TradingSnapshot:
        positions_raw = await connection.get_positions()
        orders_raw = await connection.get_orders()

        positions = [
            self._parse_position(item)
            for item in positions_raw
            if matches_magic(item, magic)
        ]
        orders = [
            self._parse_order(item)
            for item in orders_raw
            if matches_magic(item, magic)
        ]

        symbols = set(allowed_symbols)
        for item in positions:
            symbols.add(item.symbol)
        for item in orders:
            symbols.add(item.symbol)

        quotes = await self._fetch_quotes(connection, sorted(symbols))

        return TradingSnapshot(
            magic=magic,
            positions=positions,
            orders=orders,
            quotes=quotes,
        )

    async def _fetch_quotes(
        self,
        connection: Any,
        symbols: list[str],
    ) -> list[SymbolQuote]:
        quotes: list[SymbolQuote] = []

        for symbol in symbols:
            try:
                price = await connection.get_symbol_price(symbol=symbol)
                spec = await self._fetch_spec(connection, symbol)
                quotes.append(SymbolQuote(
                    symbol=symbol,
                    bid=_to_float(price.get("bid")),
                    ask=_to_float(price.get("ask")),
                    time=price.get("time"),
                    pip_size=_to_float(spec.get("pipSize")) if spec else None,
                    digits=_to_int(spec.get("digits")) if spec else None,
                ))
            except Exception as exc:
                logger.debug("Quote unavailable for %s: %s", symbol, exc)

        return quotes

    async def _fetch_spec(
        self,
        connection: Any,
        symbol: str,
    ) -> dict | None:
        try:
            return await connection.get_symbol_specification(symbol=symbol)
        except Exception as exc:
            logger.debug("Spec unavailable for %s: %s", symbol, exc)
            return None

    def _parse_position(self, raw: dict) -> PositionSnapshot:
        return PositionSnapshot(
            id=str(raw.get("id", "")),
            symbol=str(raw.get("symbol", "")),
            side=str(raw.get("type", "unknown")),
            volume=_to_float(raw.get("volume")) or 0.0,
            open_price=_to_float(raw.get("openPrice")) or 0.0,
            current_price=_to_float(raw.get("currentPrice")),
            stop_loss=_to_float(raw.get("stopLoss")),
            take_profit=_to_float(raw.get("takeProfit")),
            profit=_to_float(raw.get("profit")),
            magic=_to_int(raw.get("magic")),
        )

    def _parse_order(self, raw: dict) -> OrderSnapshot:
        return OrderSnapshot(
            id=str(raw.get("id", "")),
            symbol=str(raw.get("symbol", "")),
            order_type=str(raw.get("type", "unknown")),
            volume=_to_float(raw.get("volume")) or 0.0,
            open_price=_to_float(raw.get("openPrice")) or 0.0,
            stop_loss=_to_float(raw.get("stopLoss")),
            take_profit=_to_float(raw.get("takeProfit")),
            magic=_to_int(raw.get("magic")),
        )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
