import asyncio
import logging

from config.settings import Settings
from models.symbol_market_info import SymbolMarketInfo
from trading.mt5.connection import MT5Connection
from trading.mt5.symbol_helper import get_price_dict, get_spec_dict
from trading.mt5.trading_adapter import MT5TradingAdapter
from trading.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)


class MT5ApiFacade:
    @staticmethod
    def format_error(exc: Exception) -> str:
        return str(exc)


class MT5Service:
    """MT5 terminal servisi — serial savdo operatsiyalari."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection = MT5Connection(settings)
        self._adapter = MT5TradingAdapter(self._connection)
        self._ready = asyncio.Event()
        self._operation_lock = asyncio.Lock()
        self.api = MT5ApiFacade()

    @property
    def connection(self) -> MT5TradingAdapter:
        return self._adapter

    @property
    def is_ready(self) -> bool:
        return self._connection.is_connected

    def mark_unready(self) -> None:
        """Ulanish uzilganda stale _ready flag ni tozalash."""
        self._ready.clear()

    async def connect(self) -> None:
        await asyncio.to_thread(self._connection.connect)
        for symbol in self._settings.parsed_allowed_symbols:
            from trading.mt5.symbol_helper import ensure_symbol
            await asyncio.to_thread(ensure_symbol, symbol)
        self._ready.set()
        logger.info("MT5 service connected")

    async def disconnect(self) -> None:
        self._ready.clear()
        await asyncio.to_thread(self._connection.disconnect)

    async def ensure_ready(self) -> None:
        if self._connection.is_connected:
            if not self._ready.is_set():
                self._ready.set()
            return

        self._ready.clear()
        await self._ready.wait()
        if not self._connection.is_connected:
            raise RuntimeError("MT5 not connected")

    async def reconnect_all(self) -> None:
        self._ready.clear()
        await asyncio.to_thread(self._connection.reconnect)
        for symbol in self._settings.parsed_allowed_symbols:
            from trading.mt5.symbol_helper import ensure_symbol
            await asyncio.to_thread(ensure_symbol, symbol)
        self._ready.set()

    async def run_trading(self, operation):
        await self.ensure_ready()
        async with self._operation_lock:
            return await operation(self._adapter)

    async def fetch_snapshot(self) -> TradingSnapshot:
        await self.ensure_ready()
        async with self._operation_lock:
            return await asyncio.to_thread(self._connection.fetch_snapshot)

    async def build_market(self, symbols: set[str]) -> list[SymbolMarketInfo]:
        market: list[SymbolMarketInfo] = []
        for symbol in sorted(symbols):
            try:
                spec = await asyncio.to_thread(get_spec_dict, symbol)
                quote = await asyncio.to_thread(get_price_dict, symbol)
            except ValueError:
                continue
            market.append(SymbolMarketInfo(
                symbol=symbol,
                bid=quote.get("bid"),
                ask=quote.get("ask"),
                digits=spec.get("digits"),
                tick_size=spec.get("tickSize"),
                volume_step=spec.get("volumeStep"),
                min_volume=spec.get("minVolume"),
            ))
        return market
