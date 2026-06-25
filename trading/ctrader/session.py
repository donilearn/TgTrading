import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from ctrader_open_api import Client, Protobuf, TcpProtocol
from ctrader_open_api.endpoints import EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAErrorRes,
    ProtoOAExecutionEvent,
    ProtoOAReconcileReq,
    ProtoOAReconcileRes,
    ProtoOASpotEvent,
    ProtoOASubscribeSpotsReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolByIdRes,
    ProtoOASymbolsListReq,
    ProtoOASymbolsListRes,
)
from ctrader_open_api.protobuf import Protobuf as ProtobufExtractor

from trading.ctrader.auth import CTraderAuthService, CTraderTokens
from trading.ctrader.reactor_thread import call_from_reactor, ensure_reactor_running
from trading.ctrader.snapshot_mapper import SnapshotMapper
from trading.ctrader.spot_cache import SpotCache
from trading.ctrader.symbol_registry import SymbolRegistry
from trading.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_CONNECT_TIMEOUT = 60.0


class CTraderSession:
    """Bitta TCP sessiya — barcha yuborishlar serial (asyncio Lock)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        account_id: int,
        access_token: str,
        refresh_token: str,
        host_type: str,
        auth_service: CTraderAuthService,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._account_id = account_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._host = (
            EndPoints.PROTOBUF_LIVE_HOST
            if host_type.lower() == "live"
            else EndPoints.PROTOBUF_DEMO_HOST
        )
        self._auth = auth_service
        self._client: Client | None = None
        self._send_lock = asyncio.Lock()
        self._ready = asyncio.Event()
        self._tcp_connected = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = False
        self._symbols_loaded = False
        self.registry = SymbolRegistry()
        self.spots = SpotCache()
        self.mapper = SnapshotMapper(self.registry)
        self._event_handlers: list[Callable[[Any], None]] = []

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    def update_tokens(self, tokens: CTraderTokens) -> None:
        self._access_token = tokens.access_token
        self._refresh_token = tokens.refresh_token

    async def connect(self) -> None:
        if self._ready.is_set():
            return

        ensure_reactor_running()
        self._loop = asyncio.get_running_loop()
        self._tcp_connected.clear()
        self._ready.clear()
        connect_future: asyncio.Future = self._loop.create_future()

        def _start() -> None:
            try:
                client = Client(
                    self._host,
                    EndPoints.PROTOBUF_PORT,
                    TcpProtocol,
                    numberOfMessagesToSendPerSecond=5,
                )
                client.setConnectedCallback(self._on_connected)
                client.setDisconnectedCallback(self._on_disconnected)
                client.setMessageReceivedCallback(self._on_message)
                client.startService()
                self._client = client
                self._loop.call_soon_threadsafe(connect_future.set_result, None)
            except Exception as exc:
                self._loop.call_soon_threadsafe(connect_future.set_exception, exc)

        call_from_reactor(_start)
        await asyncio.wait_for(connect_future, timeout=_CONNECT_TIMEOUT)
        await asyncio.wait_for(self._tcp_connected.wait(), timeout=_CONNECT_TIMEOUT)
        await self._authenticate()
        await asyncio.wait_for(self._ready.wait(), timeout=_CONNECT_TIMEOUT)
        await self._load_symbols()
        logger.info("cTrader session ready account=%s host=%s", self._account_id, self._host)

    async def disconnect(self) -> None:
        self._ready.clear()
        self._connected = False
        self._symbols_loaded = False
        client = self._client
        self._client = None
        if client is None:
            return

        loop = asyncio.get_running_loop()
        done: asyncio.Future = loop.create_future()

        def _stop() -> None:
            try:
                client.stopService()
                loop.call_soon_threadsafe(done.set_result, None)
            except Exception as exc:
                loop.call_soon_threadsafe(done.set_exception, exc)

        call_from_reactor(_stop)
        await done

    async def request(self, message, timeout: float = _DEFAULT_TIMEOUT):
        """Serial yuborish — parallel requestlar navbatda."""
        async with self._send_lock:
            return await self._send_once(message, timeout)

    async def fetch_snapshot(self) -> TradingSnapshot:
        response = await self.request(self._reconcile_req())
        payload = ProtobufExtractor.extract(response)
        if not isinstance(payload, ProtoOAReconcileRes):
            raise RuntimeError(f"Unexpected reconcile response: {type(payload)}")
        return self.mapper.from_reconcile(list(payload.position), list(payload.order))

    async def subscribe_symbols(self, symbol_names: list[str]) -> None:
        symbol_ids: list[int] = []
        for name in symbol_names:
            symbol_id = self.registry.resolve_id(name)
            if symbol_id is not None:
                symbol_ids.append(symbol_id)
            else:
                logger.warning("cTrader symbol not found: %s", name)

        if not symbol_ids:
            return

        req = ProtoOASubscribeSpotsReq()
        req.ctidTraderAccountId = self._account_id
        req.symbolId.extend(symbol_ids)
        await self.request(req)

    def _reconcile_req(self) -> ProtoOAReconcileReq:
        req = ProtoOAReconcileReq()
        req.ctidTraderAccountId = self._account_id
        return req

    async def _load_symbols(self) -> None:
        if self._symbols_loaded:
            return

        list_res = await self.request(self._symbols_list_req())
        list_payload = ProtobufExtractor.extract(list_res)
        if not isinstance(list_payload, ProtoOASymbolsListRes):
            raise RuntimeError("Failed to load symbol list")

        for item in list_payload.symbol:
            self.registry.register_light(item.symbolId, item.symbolName)

        self._symbols_loaded = True

    async def load_specs_for_symbols(self, symbol_names: list[str]) -> None:
        symbol_ids: list[int] = []
        for name in symbol_names:
            symbol_id = self.registry.resolve_id(name)
            if symbol_id is not None and symbol_id not in self.registry._specs:
                symbol_ids.append(symbol_id)
        if not symbol_ids:
            return

        detail_req = ProtoOASymbolByIdReq()
        detail_req.ctidTraderAccountId = self._account_id
        detail_req.symbolId.extend(symbol_ids)
        detail_res = await self.request(detail_req, timeout=60.0)
        detail_payload = ProtobufExtractor.extract(detail_res)
        if isinstance(detail_payload, ProtoOASymbolByIdRes):
            for symbol in detail_payload.symbol:
                spec = _symbol_spec_dict(symbol)
                spec["symbolName"] = self.registry.resolve_name(symbol.symbolId)
                self.registry.register_spec(symbol.symbolId, spec)

    def _symbols_list_req(self) -> ProtoOASymbolsListReq:
        req = ProtoOASymbolsListReq()
        req.ctidTraderAccountId = self._account_id
        return req

    async def _send_once(self, message, timeout: float):
        client = self._client
        if client is None or not self._connected:
            raise RuntimeError("cTrader not connected")

        loop = self._loop
        future: asyncio.Future = loop.create_future()
        msg_id = uuid.uuid4().hex

        def _on_success(response) -> None:
            if not future.done():
                loop.call_soon_threadsafe(future.set_result, response)

        def _on_error(failure) -> None:
            if not future.done():
                loop.call_soon_threadsafe(
                    future.set_exception,
                    failure.value if hasattr(failure, "value") else failure,
                )

        def _do_send() -> None:
            try:
                deferred = client.send(
                    message,
                    clientMsgId=msg_id,
                    responseTimeoutInSeconds=int(timeout),
                )
                deferred.addCallbacks(_on_success, _on_error)
            except Exception as exc:
                loop.call_soon_threadsafe(future.set_exception, exc)

        call_from_reactor(_do_send)
        response = await asyncio.wait_for(future, timeout=timeout + 5)
        self._raise_on_error(response)
        return response

    def _raise_on_error(self, message) -> None:
        payload_type = message.payloadType
        if payload_type == ProtoOAErrorRes().payloadType:
            err = ProtobufExtractor.extract(message)
            raise RuntimeError(f"cTrader error {err.errorCode}: {err.description}")

    def _on_connected(self, _client) -> None:
        logger.info("cTrader TCP connected")
        self._connected = True
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._tcp_connected.set)

    def _on_disconnected(self, _client, reason) -> None:
        logger.warning("cTrader disconnected: %s", reason)
        self._connected = False
        self._ready.clear()

    def _on_message(self, _client, message) -> None:
        payload_type = message.payloadType

        if payload_type == ProtoOASpotEvent().payloadType:
            event = ProtobufExtractor.extract(message)
            self.spots.update(event.symbolId, event.bid, event.ask)
            return

        if payload_type == ProtoOAExecutionEvent().payloadType:
            for handler in self._event_handlers:
                handler(ProtobufExtractor.extract(message))

    async def _authenticate(self) -> None:
        try:
            app_req = ProtoOAApplicationAuthReq()
            app_req.clientId = self._client_id
            app_req.clientSecret = self._client_secret
            await self.request(app_req, timeout=_CONNECT_TIMEOUT)

            account_req = ProtoOAAccountAuthReq()
            account_req.ctidTraderAccountId = self._account_id
            account_req.accessToken = self._access_token
            await self.request(account_req, timeout=_CONNECT_TIMEOUT)
            self._ready.set()
        except Exception as exc:
            logger.warning("cTrader auth failed, refreshing token: %s", exc)
            await self._refresh_and_retry_auth()

    async def _refresh_and_retry_auth(self) -> None:
        tokens = await self._auth.refresh(self._refresh_token)
        self.update_tokens(tokens)
        account_req = ProtoOAAccountAuthReq()
        account_req.ctidTraderAccountId = self._account_id
        account_req.accessToken = self._access_token
        await self.request(account_req, timeout=_CONNECT_TIMEOUT)
        self._ready.set()


def _symbol_spec_dict(symbol) -> dict:
    from trading.ctrader.converters import tick_size_from_digits

    digits = symbol.digits
    step = symbol.stepVolume / 100.0 if symbol.stepVolume else 0.01
    min_vol = symbol.minVolume / 100.0 if symbol.minVolume else 0.01
    return {
        "symbolId": symbol.symbolId,
        "symbolName": None,
        "digits": digits,
        "tickSize": tick_size_from_digits(digits),
        "volumeStep": step,
        "minVolume": min_vol,
        "pipPosition": symbol.pipPosition,
    }
