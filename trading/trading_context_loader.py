import asyncio
import logging

from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.client import MetaApiService
from trading.existing_orders_service import ExistingOrdersService
from trading.market_context_service import MarketContextService
from trading.metaapi_trading_snapshot import MetaApiTradingSnapshotService

logger = logging.getLogger(__name__)

_META_CONTEXT_TIMEOUT = 45.0


class TradingContextLoader:
    def __init__(
        self,
        metaapi: MetaApiService,
        existing_orders: ExistingOrdersService,
        market_context: MarketContextService,
    ) -> None:
        self._metaapi = metaapi
        self._existing_orders = existing_orders
        self._market_context = market_context
        self._snapshot = MetaApiTradingSnapshotService()

    async def load(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        try:
            return await asyncio.wait_for(
                self._load_once(magic, group_magics),
                timeout=_META_CONTEXT_TIMEOUT,
            )
        except TimeoutError:
            logger.error(
                "MetaAPI context timeout (%ss) for chat=%s magic=%s — reconnecting",
                _META_CONTEXT_TIMEOUT,
                chat_id,
                magic,
            )
            await self._metaapi.recover_after_timeout()
            return await asyncio.wait_for(
                self._load_once(magic, group_magics),
                timeout=_META_CONTEXT_TIMEOUT,
            )

    async def _load_once(
        self,
        magic: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        async def load_op(connection):
            snapshot = await self._snapshot.fetch(connection)
            existing = self._existing_orders.from_snapshot(snapshot, magic)
            market = await self._market_context.build(connection, existing)
            global_count = self._existing_orders.count_for_magics(
                snapshot,
                group_magics,
            )
            return existing, market, global_count

        return await self._metaapi.run_rpc(load_op)
