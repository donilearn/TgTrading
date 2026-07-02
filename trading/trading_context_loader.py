import asyncio
import logging
from typing import TYPE_CHECKING

from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.existing_orders_service import ExistingOrdersService
from trading.metaapi.terminal_reader import MetaApiTerminalReader

if TYPE_CHECKING:
    from trading.mt5.service import MT5Service

logger = logging.getLogger(__name__)

_META_CONTEXT_TIMEOUT = 30.0


class TradingContextLoader:
    def __init__(
        self,
        trading,
        existing_orders: ExistingOrdersService,
        settings: Settings,
        *,
        win_mode: bool,
    ) -> None:
        self._trading = trading
        self._existing_orders = existing_orders
        self._settings = settings
        self._win_mode = win_mode
        self._meta_reader = MetaApiTerminalReader() if not win_mode else None

    async def load(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        if self._win_mode:
            return await self._load_mt5(magic, chat_id, group_magics)
        return await self._load_metaapi(magic, chat_id, group_magics)

    async def _load_mt5(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        service: "MT5Service" = self._trading
        snapshot = await service.fetch_snapshot()
        existing = self._existing_orders.from_snapshot(snapshot, magic)
        symbols = set(self._settings.parsed_allowed_symbols)
        symbols.update(order.symbol for order in existing)
        market = await service.build_market(symbols)
        global_count = self._existing_orders.count_for_magics(snapshot, group_magics)

        logger.debug(
            "Context loaded (MT5) chat=%s magic=%s orders=%d market=%d",
            chat_id,
            magic,
            len(existing),
            len(market),
        )
        return existing, market, global_count

    async def _load_metaapi(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        return await asyncio.wait_for(
            self._load_metaapi_once(magic, chat_id, group_magics),
            timeout=_META_CONTEXT_TIMEOUT,
        )

    async def _load_metaapi_once(
        self,
        magic: int,
        chat_id: int,
        group_magics: list[int],
    ) -> tuple[list[ExistingOrder], list[SymbolMarketInfo], int]:
        await self._trading.ensure_streaming_ready()
        terminal = self._trading.streaming_connection.terminal_state
        snapshot = self._meta_reader.read_snapshot(terminal)

        existing = self._existing_orders.from_snapshot(snapshot, magic)
        symbols = set(self._settings.parsed_allowed_symbols)
        symbols.update(order.symbol for order in existing)
        market = self._meta_reader.read_market(terminal, symbols)
        global_count = self._existing_orders.count_for_magics(snapshot, group_magics)

        logger.debug(
            "Context loaded (MetaAPI) chat=%s magic=%s orders=%d market=%d",
            chat_id,
            magic,
            len(existing),
            len(market),
        )
        return existing, market, global_count
