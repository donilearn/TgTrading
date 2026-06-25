import logging

from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.existing_orders_service import ExistingOrdersService
from trading.mt5.service import MT5Service

logger = logging.getLogger(__name__)


class TradingContextLoader:
    def __init__(
        self,
        mt5: MT5Service,
        existing_orders: ExistingOrdersService,
        settings: Settings,
    ) -> None:
        self._mt5 = mt5
        self._existing_orders = existing_orders
        self._settings = settings

    async def load(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        snapshot = await self._mt5.fetch_snapshot()
        existing = self._existing_orders.from_snapshot(snapshot, magic)
        symbols = set(self._settings.parsed_allowed_symbols)
        symbols.update(order.symbol for order in existing)
        market = await self._mt5.build_market(symbols)
        global_count = self._existing_orders.count_for_magics(snapshot, group_magics)

        logger.debug(
            "Context loaded chat=%s magic=%s orders=%d market=%d",
            chat_id,
            magic,
            len(existing),
            len(market),
        )
        return existing, market, global_count
