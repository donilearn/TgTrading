import logging
from typing import Any

from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.symbol_spec_cache import SymbolSpecCache

logger = logging.getLogger(__name__)


class MarketContextService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._spec_cache = SymbolSpecCache()

    async def build(
        self,
        connection: Any,
        existing_orders: list[ExistingOrder],
    ) -> list[SymbolMarketInfo]:
        symbols = set(self._settings.parsed_allowed_symbols)
        for order in existing_orders:
            symbols.add(order.symbol)

        market: list[SymbolMarketInfo] = []
        for symbol in sorted(symbols):
            try:
                spec = await self._spec_cache.get(connection, symbol)
                quote = await self._spec_cache.get_price(connection, symbol)
                market.append(SymbolMarketInfo(
                    symbol=symbol,
                    bid=_float(quote.get("bid")),
                    ask=_float(quote.get("ask")),
                    digits=_int(spec.get("digits")),
                    tick_size=_float(spec.get("tickSize")),
                    volume_step=_float(spec.get("volumeStep")),
                    min_volume=_float(spec.get("minVolume")),
                ))
            except Exception as exc:
                logger.debug("Market context unavailable for %s: %s", symbol, exc)

        return market


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
