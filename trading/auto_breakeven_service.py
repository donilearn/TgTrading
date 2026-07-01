import asyncio
import logging

from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.pip_profit_calculator import position_profit_pips
from trading.price_normalizer import normalize_price
from trading.symbol_spec_cache import SymbolSpecCache
from trading.trade_retry import run_trade_with_retry

logger = logging.getLogger(__name__)

_MODIFY_DELAY_SEC = 0.35


class AutoBreakevenService:
    """Har Telegram xabarida ochiq pozitsiyalarni tekshiradi: profit >= pip → SL=openPrice."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._spec_cache = SymbolSpecCache()

    async def apply_on_message(
        self,
        trading,
        existing: list[ExistingOrder],
        market: list[SymbolMarketInfo],
    ) -> bool:
        threshold = self._settings.auto_be_pips
        if threshold <= 0:
            return False

        market_by_symbol = {item.symbol: item for item in market}
        positions = [item for item in existing if item.is_position]
        if not positions:
            return False

        changed = False
        for position in positions:
            market_info = market_by_symbol.get(position.symbol)
            applied = await self._try_breakeven(
                trading,
                position,
                market_info,
                threshold,
            )
            if applied:
                changed = True
                await asyncio.sleep(_MODIFY_DELAY_SEC)

        return changed

    async def _try_breakeven(
        self,
        trading,
        position: ExistingOrder,
        market_info: SymbolMarketInfo | None,
        threshold_pips: float,
    ) -> bool:
        if not self._settings.trading_enabled:
            profit = await self._profit_pips_for_log(trading, position, market_info)
            if profit is not None and profit >= threshold_pips:
                logger.info(
                    "DRY-RUN auto-BE: #%s %s profit=%.1f pips (threshold=%s)",
                    position.order_number,
                    position.symbol,
                    profit,
                    threshold_pips,
                )
            return False

        async def _modify(connection):
            spec = await self._spec_cache.get(connection, position.symbol)
            if not _sl_needs_breakeven(position, spec):
                return False

            profit_pips = position_profit_pips(position, market_info, spec)
            if profit_pips is None or profit_pips < threshold_pips:
                return False

            be_sl = normalize_price(position.open_price, spec)
            await connection.modify_position(
                position_id=position.order_number,
                stop_loss=be_sl,
            )
            logger.info(
                "Auto-BE #%s %s %s profit=%.1f pips → SL=%s",
                position.order_number,
                position.symbol,
                position.side,
                profit_pips,
                be_sl,
            )
            return True

        return await run_trade_with_retry(trading, _modify)

    async def _profit_pips_for_log(
        self,
        trading,
        position: ExistingOrder,
        market_info: SymbolMarketInfo | None,
    ) -> float | None:
        async def _read(connection):
            spec = await self._spec_cache.get(connection, position.symbol)
            return position_profit_pips(position, market_info, spec)

        try:
            return await run_trade_with_retry(trading, _read)
        except Exception:
            return None


def _sl_needs_breakeven(position: ExistingOrder, spec: dict) -> bool:
    open_price = normalize_price(position.open_price, spec)
    if open_price is None:
        return False

    sl = normalize_price(position.stop_loss, spec)
    if sl is None:
        return True

    side = position.side.lower()
    if side == "buy":
        return sl < open_price
    if side == "sell":
        return sl > open_price
    return False
