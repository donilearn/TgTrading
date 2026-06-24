import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from metaapi_cloud_sdk import MetaApi

from config.settings import Settings
from trading.metaapi_account_checker import ensure_account_ready

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RECONNECT_SETTLE_SEC = 2.0
_CONNECT_RETRY_DELAY_SEC = 5.0
_MAX_CONNECT_ATTEMPTS = 6
_SYNC_TIMEOUT_SEC = 300.0
_WAIT_READY_TIMEOUT_SEC = 45.0


def _is_rate_limited(exc: Exception) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return "toomanyrequests" in name.lower() or "too many" in text


def _is_retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    hints = (
        "timed out",
        "timeout",
        "not connected",
        "connection closed",
        "disconnected",
        "not synchronized",
        "failed to connect",
        "socket client",
    )
    return any(hint in text for hint in hints)


class MetaApiService:
    """Streaming (o'qish) + RPC (savdo) — fon keeper bilan doim tayyor."""

    def __init__(self, settings: Settings) -> None:
        self._api = MetaApi(token=settings.metaapi_token)
        self._account_id = settings.metaapi_account_id
        self._account = None
        self._streaming_connection = None
        self._rpc_connection = None
        self._lifecycle_lock = asyncio.Lock()
        self._rpc_lock = asyncio.Lock()
        self._streaming_ready = asyncio.Event()
        self._rpc_ready = asyncio.Event()
        self._reconnect_requested = asyncio.Event()
        self._keeper = None
        self._market_symbols: list[str] = []
        self._last_connect_at = 0.0
        self._reconnect_in_progress = False

    @property
    def last_connect_at(self) -> float:
        return self._last_connect_at

    @property
    def api(self) -> MetaApi:
        return self._api

    @property
    def reconnect_pending(self) -> bool:
        return self._reconnect_requested.is_set()

    @property
    def connection(self):
        if self._rpc_connection is None:
            raise RuntimeError("MetaAPI RPC connection is not established")
        return self._rpc_connection

    @property
    def streaming_connection(self):
        if self._streaming_connection is None:
            raise RuntimeError("MetaAPI streaming connection is not established")
        return self._streaming_connection

    def attach_keeper(self, keeper: Any) -> None:
        self._keeper = keeper

    def request_reconnect(self) -> None:
        self._streaming_ready.clear()
        self._rpc_ready.clear()
        self._reconnect_requested.set()

    async def connect(self) -> None:
        async with self._lifecycle_lock:
            if self._streaming_ready.is_set() and self._rpc_ready.is_set():
                return
            await self._connect_all_inner()

    async def ensure_streaming_ready(self) -> None:
        await self._wait_until_ready(
            self._streaming_ready,
            "streaming",
            timeout=_WAIT_READY_TIMEOUT_SEC,
        )

    async def ensure_rpc_ready(self) -> None:
        await self._wait_until_ready(
            self._rpc_ready,
            "RPC",
            timeout=_WAIT_READY_TIMEOUT_SEC,
        )

    async def run_rpc(
        self,
        operation: Callable[[Any], Awaitable[T]],
    ) -> T:
        await self.ensure_rpc_ready()
        async with self._rpc_lock:
            try:
                return await operation(self.connection)
            except Exception as exc:
                if not _is_retryable(exc):
                    raise
                logger.warning("MetaAPI RPC error, waiting for reconnect: %s", exc)
                self.request_reconnect()
                await self.ensure_rpc_ready()
                return await operation(self.connection)

    async def check_health(self) -> bool:
        if not self._streaming_ready.is_set() or not self._rpc_ready.is_set():
            return False

        streaming = self._streaming_connection
        rpc = self._rpc_connection
        if streaming is None or rpc is None:
            return False

        try:
            terminal = streaming.terminal_state
            if not terminal.connected or not terminal.connected_to_broker:
                return False

            inner = rpc._meta_api_connection
            if not inner.is_synchronized():
                return False
        except Exception as exc:
            logger.debug("MetaAPI health check failed: %s", exc)
            return False

        return True

    async def reconnect_all(self) -> None:
        if self._reconnect_in_progress:
            return
        self._reconnect_in_progress = True
        try:
            await self._reconnect_all_inner()
        finally:
            self._reconnect_in_progress = False

    async def _reconnect_all_inner(self) -> None:
        async with self._lifecycle_lock:
            self._streaming_ready.clear()
            self._rpc_ready.clear()
            self._reconnect_requested.clear()

            for attempt in range(1, _MAX_CONNECT_ATTEMPTS + 1):
                try:
                    await self._close_connections_unlocked()
                    if attempt > 2:
                        await self._reset_websocket_client()
                    await self._connect_all_inner()
                    await self._resubscribe_market_data()
                    logger.info("MetaAPI reconnected (attempt %d)", attempt)
                    return
                except Exception as exc:
                    delay = _CONNECT_RETRY_DELAY_SEC * attempt
                    if _is_rate_limited(exc):
                        delay *= 2
                    logger.warning(
                        "MetaAPI reconnect attempt %d/%d failed: %s — retry in %.0fs",
                        attempt,
                        _MAX_CONNECT_ATTEMPTS,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

            logger.error("MetaAPI reconnect exhausted after %d attempts", _MAX_CONNECT_ATTEMPTS)

    async def disconnect(self) -> None:
        async with self._lifecycle_lock:
            async with self._rpc_lock:
                self._streaming_ready.clear()
                self._rpc_ready.clear()
                await self._close_connections_unlocked()
            await self._reset_websocket_client()
            logger.info("MetaAPI disconnected")

    async def _wait_until_ready(
        self,
        event: asyncio.Event,
        label: str,
        timeout: float = _WAIT_READY_TIMEOUT_SEC,
    ) -> None:
        if event.is_set():
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        logged = False

        while not event.is_set():
            if loop.time() >= deadline:
                self.request_reconnect()
                raise TimeoutError(
                    f"MetaAPI {label} connection not ready within {timeout:.0f}s",
                )

            if self._reconnect_requested.is_set() and self._keeper is not None:
                self._keeper.request_reconnect()

            if not logged:
                logger.info("Waiting for MetaAPI %s connection...", label)
                logged = True

            remaining = max(0.1, deadline - loop.time())
            wait_tasks = [
                asyncio.create_task(event.wait(), name=f"metaapi-{label}-ready"),
                asyncio.create_task(
                    self._reconnect_requested.wait(),
                    name=f"metaapi-{label}-reconnect",
                ),
            ]
            done, pending = await asyncio.wait(
                wait_tasks,
                timeout=min(remaining, 5.0),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            if event.is_set():
                return

            if not done:
                continue

            await asyncio.sleep(0.5)

    async def _connect_all_inner(self) -> None:
        account = self._account
        if account is None:
            account = await self._api.metatrader_account_api.get_account(
                self._account_id,
            )
            await ensure_account_ready(account)
            self._account = account

        await account.wait_connected()

        streaming = account.get_streaming_connection()
        await streaming.connect()
        await streaming.wait_synchronized({"timeoutInSeconds": _SYNC_TIMEOUT_SEC})
        self._streaming_connection = streaming
        self._streaming_ready.set()

        rpc = account.get_rpc_connection()
        await rpc.connect()
        await rpc.wait_synchronized(_SYNC_TIMEOUT_SEC)
        self._rpc_connection = rpc
        self._rpc_ready.set()

        await asyncio.sleep(_RECONNECT_SETTLE_SEC)
        self._last_connect_at = asyncio.get_running_loop().time()
        logger.info("MetaAPI streaming + RPC ready for account %s", self._account_id)

    async def subscribe_market_data(self, symbols: list[str]) -> None:
        self._market_symbols = list(symbols)
        await self._resubscribe_market_data()

    async def _resubscribe_market_data(self) -> None:
        if not self._market_symbols:
            return
        await self.ensure_streaming_ready()
        connection = self.streaming_connection
        for symbol in self._market_symbols:
            try:
                await connection.subscribe_to_market_data(symbol)
            except Exception as exc:
                logger.debug("Market data subscribe %s: %s", symbol, exc)

    async def _close_connections_unlocked(self) -> None:
        streaming = self._streaming_connection
        rpc = self._rpc_connection
        self._streaming_connection = None
        self._rpc_connection = None

        if streaming is not None:
            await self._close_connection(streaming)
        if rpc is not None:
            await self._close_connection(rpc)

        if streaming is not None or rpc is not None:
            await asyncio.sleep(_RECONNECT_SETTLE_SEC)

    async def _close_connection(self, connection) -> None:
        try:
            if getattr(connection, "_closed", False):
                return
            inner = connection._meta_api_connection
            await inner.close(connection.instance_id)
            connection._closed = True
        except KeyError:
            pass
        except Exception as exc:
            logger.debug("MetaAPI connection close: %s", exc)

    async def _reset_websocket_client(self) -> None:
        try:
            ws_client = self._api._metaapi_websocket_client
            await ws_client.close()
            ws_client.stop()
        except Exception as exc:
            logger.debug("MetaAPI websocket reset: %s", exc)

        try:
            self._api._terminal_hash_manager._stop()
        except Exception:
            pass

        await asyncio.sleep(0.5)
