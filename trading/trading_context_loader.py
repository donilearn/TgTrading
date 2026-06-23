import asyncio
import logging

from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.client import MetaApiService
from trading.existing_orders_service import ExistingOrdersService
from trading.market_context_service import MarketContextService

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

    async def load(self, magic: int, chat_id: int) -> tuple[list[ExistingOrder], list[SymbolMarketInfo]]:
        try:
            return await asyncio.wait_for(
                self._load_once(magic),
                timeout=_META_CONTEXT_TIMEOUT,
            )
        except TimeoutError:
            logger.error(
                "MetaAPI context timeout (%ss) for chat=%s magic=%s — reconnecting",
                _META_CONTEXT_TIMEOUT,
                chat_id,
                magic,
            )
            await self._recover_connection()
            return await asyncio.wait_for(
                self._load_once(magic),
                timeout=_META_CONTEXT_TIMEOUT,
            )

    async def _load_once(self, magic: int) -> tuple[list[ExistingOrder], list[SymbolMarketInfo]]:
        await self._metaapi.ensure_ready()
        existing = await self._existing_orders.fetch(self._metaapi.connection, magic)
        market = await self._market_context.build(self._metaapi.connection, existing)
        return existing, market

    async def _recover_connection(self) -> None:
        try:
            await self._metaapi.reconnect_rpc()
        except Exception:
            logger.exception("MetaAPI RPC reconnect failed, full reconnect")
            await self._metaapi.disconnect()
            await self._metaapi.connect()
