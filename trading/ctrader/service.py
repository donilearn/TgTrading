import asyncio
import logging

from config.settings import Settings
from models.symbol_market_info import SymbolMarketInfo
from trading.ctrader.auth import CTraderAuthService
from trading.ctrader.session import CTraderSession
from trading.ctrader.trading_adapter import CTraderTradingAdapter
from trading.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)


class CTraderApiFacade:
    """error_formatter uchun minimal API facade."""

    @staticmethod
    def format_error(exc: Exception) -> str:
        return str(exc)


class CTraderService:
    """Asosiy cTrader servisi — bitta sessiya, serial requestlar."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._auth = CTraderAuthService(
            settings.ctrader_client_id,
            settings.ctrader_client_secret,
            settings.ctrader_redirect_uri,
        )
        self._session = CTraderSession(
            client_id=settings.ctrader_client_id,
            client_secret=settings.ctrader_client_secret,
            account_id=settings.ctrader_account_id,
            access_token=settings.ctrader_access_token,
            refresh_token=settings.ctrader_refresh_token,
            host_type=settings.ctrader_host_type,
            auth_service=self._auth,
        )
        self._adapter = CTraderTradingAdapter(self._session)
        self._ready = asyncio.Event()
        self._operation_lock = asyncio.Lock()
        self.api = CTraderApiFacade()

    @property
    def connection(self) -> CTraderTradingAdapter:
        return self._adapter

    @property
    def is_ready(self) -> bool:
        return self._session.is_ready

    async def connect(self) -> None:
        await self._session.connect()
        await self._session.load_specs_for_symbols(self._settings.parsed_allowed_symbols)
        await self._session.subscribe_symbols(self._settings.parsed_allowed_symbols)
        self._ready.set()
        logger.info("cTrader service connected")

    async def disconnect(self) -> None:
        self._ready.clear()
        await self._session.disconnect()

    async def ensure_ready(self) -> None:
        if self._session.is_ready:
            return
        await self._ready.wait()

    async def reconnect_all(self) -> None:
        await self.disconnect()
        await asyncio.sleep(2.0)
        await self.connect()

    async def run_trading(self, operation):
        """Barcha savdo operatsiyalari ketma-ket — server parallel deny qilmasin."""
        await self.ensure_ready()
        async with self._operation_lock:
            return await operation(self._adapter)

    async def fetch_snapshot(self) -> TradingSnapshot:
        await self.ensure_ready()
        async with self._operation_lock:
            return await self._session.fetch_snapshot()

    def build_market(self, symbols: set[str]) -> list[SymbolMarketInfo]:
        market: list[SymbolMarketInfo] = []
        for symbol in sorted(symbols):
            symbol_id = self._session.registry.resolve_id(symbol)
            if symbol_id is None:
                continue
            spec = self._session.registry.get_spec(symbol) or {}
            quote = self._session.spots.get(symbol_id)
            market.append(SymbolMarketInfo(
                symbol=symbol,
                bid=quote.bid if quote else None,
                ask=quote.ask if quote else None,
                digits=spec.get("digits"),
                tick_size=spec.get("tickSize"),
                volume_step=spec.get("volumeStep"),
                min_volume=spec.get("minVolume"),
            ))
        return market
