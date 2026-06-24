import asyncio
import logging

from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.client import MetaApiService
from trading.existing_orders_service import ExistingOrdersService
from trading.metaapi_terminal_reader import MetaApiTerminalReader

logger = logging.getLogger(__name__)

_META_CONTEXT_TIMEOUT = 45.0


class TradingContextLoader:
    def __init__(
        self,
        metaapi: MetaApiService,
        existing_orders: ExistingOrdersService,
        settings: Settings,
    ) -> None:
        self._metaapi = metaapi
        self._existing_orders = existing_orders
        self._settings = settings
        self._reader = MetaApiTerminalReader()

    async def load(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        try:
            return await asyncio.wait_for(
                self._load_once(magic, chat_id, group_magics),
                timeout=_META_CONTEXT_TIMEOUT,
            )
        except TimeoutError:
            logger.error(
                "MetaAPI context timeout (%ss) for chat=%s magic=%s — reconnecting",
                _META_CONTEXT_TIMEOUT,
                chat_id,
                magic,
            )
            await self._metaapi.reconnect_all()
            return await asyncio.wait_for(
                self._load_once(magic, chat_id, group_magics),
                timeout=_META_CONTEXT_TIMEOUT,
            )

    async def _load_once(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        await self._metaapi.ensure_streaming_ready()
        terminal = self._metaapi.streaming_connection.terminal_state
        snapshot = self._reader.read_snapshot(terminal)

        existing = self._existing_orders.from_snapshot(snapshot, magic)
        symbols = set(self._settings.parsed_allowed_symbols)
        symbols.update(order.symbol for order in existing)
        market = self._reader.read_market(terminal, symbols)
        global_count = self._existing_orders.count_for_magics(snapshot, group_magics)

        logger.debug(
            "Context loaded chat=%s magic=%s orders=%d market=%d",
            chat_id,
            magic,
            len(existing),
            len(market),
        )
        return existing, market, global_count
