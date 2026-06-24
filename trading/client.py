import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from metaapi_cloud_sdk import MetaApi

from config.settings import Settings
from trading.metaapi_account_checker import ensure_account_ready

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RECONNECT_SETTLE_SEC = 3.0
_STREAMING_RPC_GAP_SEC = 5.0
_CONNECT_RETRY_DELAY_SEC = 5.0
_MAX_CONNECT_ATTEMPTS = 6
_SYNC_TIMEOUT_SEC = 120.0
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
        "failed to subscribe",
    )
    return any(hint in text for hint in hints)


class MetaApiService:
    """Streaming (context) + lazy RPC (savdo) — bitta reconnect, atomic swap."""

    def __init__(self, settings: Settings) -> None:
        self._api = MetaApi(token=settings.metaapi_token)
        self._account_id = settings.metaapi_account_id
        self._account = None
        self._streaming_connection = None
        self._rpc_connection = None
        # Lock ordering: always _lifecycle_lock before _rpc_lock.
        # Never call reconnect_all() while holding _rpc_lock.
        self._lifecycle_lock = asyncio.Lock()
        self._rpc_lock = asyncio.Lock()
        self._streaming_ready = asyncio.Event()
        self._rpc_ready = asyncio.Event()
        self._reconnect_requested = asyncio.Event()
        self._keeper = None
        self._market_symbols: list[str] = []
        self._last_connect_at = 0.0
        self._reconnect_task: asyncio.Task | None = None

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
    def reconnect_in_progress(self) -> bool:
        return self._reconnect_task is not None and not self._reconnect_task.done()

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
        self._reconnect_requested.set()
        if self._keeper is not None:
            self._keeper.schedule_reconnect()

    async def connect(self) -> None:
        """Startup: faqat streaming — RPC savdo vaqtida lazy ulanadi."""
        async with self._lifecycle_lock:
            if self._streaming_ready.is_set():
                return
            streaming = await self._open_streaming_connection()
            self._streaming_connection = streaming
            self._streaming_ready.set()
            self._last_connect_at = asyncio.get_running_loop().time()
            logger.info("MetaAPI streaming ready for account %s", self._account_id)

    async def ensure_streaming_ready(self) -> None:
        await self._wait_until_ready(
            self._streaming_ready,
            "streaming",
            timeout=_WAIT_READY_TIMEOUT_SEC,
        )

    async def ensure_rpc_ready(self) -> None:
        await self.ensure_streaming_ready()
        if self._rpc_ready.is_set():
            return
        async with self._lifecycle_lock:
            if self._rpc_ready.is_set():
                return
            await asyncio.sleep(_STREAMING_RPC_GAP_SEC)
            rpc = await self._open_rpc_connection()
            self._rpc_connection = rpc
            self._rpc_ready.set()
            logger.info("MetaAPI RPC ready (lazy) for account %s", self._account_id)

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
                logger.warning("MetaAPI RPC error, reconnecting: %s", exc)

        await self.reconnect_all()
        await self.ensure_rpc_ready()
        async with self._rpc_lock:
            return await operation(self.connection)

    async def check_health(self) -> bool:
        if not self._streaming_ready.is_set():
            return False

        streaming = self._streaming_connection
        if streaming is None:
            return False

        try:
            terminal = streaming.terminal_state
            if not terminal.connected or not terminal.connected_to_broker:
                return False
        except Exception as exc:
            logger.debug("MetaAPI health check failed: %s", exc)
            return False

        if self._rpc_ready.is_set() and self._rpc_connection is not None:
            try:
                inner = self._rpc_connection._meta_api_connection
                if not inner.is_synchronized():
                    return False
            except Exception as exc:
                logger.debug("MetaAPI RPC health check failed: %s", exc)
                return False

        return True

    async def reconnect_all(self) -> None:
        if self._reconnect_task is not None and not self._reconnect_task.done():
            await self._reconnect_task
            return

        self._reconnect_task = asyncio.create_task(
            self._reconnect_all_inner(),
            name="metaapi-reconnect-all",
        )
        try:
            await self._reconnect_task
        finally:
            if self._reconnect_task is not None and self._reconnect_task.done():
                self._reconnect_task = None

    async def disconnect(self) -> None:
        async with self._lifecycle_lock:
            async with self._rpc_lock:
                await self._invalidate_rpc_unlocked()
                streaming = self._streaming_connection
                self._streaming_connection = None
                self._streaming_ready.clear()
                if streaming is not None:
                    await self._close_connection(streaming)
            await self._reset_websocket_client()
            logger.info("MetaAPI disconnected")

    async def subscribe_market_data(self, symbols: list[str]) -> None:
        self._market_symbols = list(symbols)
        await self._resubscribe_market_data()

    async def _reconnect_all_inner(self) -> None:
        self._reconnect_requested.clear()

        for attempt in range(1, _MAX_CONNECT_ATTEMPTS + 1):
            try:
                async with self._lifecycle_lock:
                    if attempt > 2:
                        await self._reset_websocket_client()
                    await self._invalidate_rpc_unlocked()
                    new_streaming = await self._open_streaming_connection()
                    await self._swap_streaming_connection(new_streaming)
                    await asyncio.sleep(_RECONNECT_SETTLE_SEC)
                    await self._resubscribe_market_data_unlocked()
                    self._last_connect_at = asyncio.get_running_loop().time()
                    logger.info("MetaAPI streaming reconnected (attempt %d)", attempt)
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

        while not event.is_set():
            remaining = deadline - loop.time()
            if remaining <= 0:
                logger.warning("MetaAPI %s not ready in %.0fs — forcing reconnect", label, timeout)
                await self.reconnect_all()
                if event.is_set():
                    return
                raise TimeoutError(
                    f"MetaAPI {label} connection not ready within {timeout:.0f}s",
                )

            if self.reconnect_in_progress and self._reconnect_task is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._reconnect_task),
                        timeout=remaining,
                    )
                except TimeoutError:
                    continue
                if event.is_set():
                    return
                continue

            if self._reconnect_requested.is_set() and self._keeper is not None:
                await self._keeper.reconnect_and_wait()
                continue

            try:
                await asyncio.wait_for(event.wait(), timeout=min(remaining, 5.0))
            except TimeoutError:
                continue

    async def _get_account(self) -> Any:
        account = self._account
        if account is None:
            account = await self._api.metatrader_account_api.get_account(
                self._account_id,
            )
            await ensure_account_ready(account)
            self._account = account
        await account.wait_connected()
        return account

    async def _open_streaming_connection(self) -> Any:
        account = await self._get_account()
        streaming = account.get_streaming_connection()
        await streaming.connect()
        await streaming.wait_synchronized({"timeoutInSeconds": _SYNC_TIMEOUT_SEC})
        return streaming

    async def _open_rpc_connection(self) -> Any:
        account = await self._get_account()
        rpc = account.get_rpc_connection()
        await rpc.connect()
        await rpc.wait_synchronized(_SYNC_TIMEOUT_SEC)
        return rpc

    async def _swap_streaming_connection(self, new_connection: Any) -> None:
        old = self._streaming_connection
        self._streaming_connection = new_connection
        self._streaming_ready.set()
        if old is not None and old is not new_connection:
            await self._close_connection(old)

    async def _invalidate_rpc_unlocked(self) -> None:
        self._rpc_ready.clear()
        rpc = self._rpc_connection
        self._rpc_connection = None
        if rpc is not None:
            await self._close_connection(rpc)

    async def _resubscribe_market_data(self) -> None:
        await self.ensure_streaming_ready()
        await self._resubscribe_market_data_unlocked()

    async def _resubscribe_market_data_unlocked(self) -> None:
        if not self._market_symbols or self._streaming_connection is None:
            return

        connection = self._streaming_connection
        for symbol in self._market_symbols:
            try:
                await connection.subscribe_to_market_data(symbol)
                await asyncio.sleep(0.3)
            except Exception as exc:
                logger.debug("Market data subscribe %s: %s", symbol, exc)

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

        await asyncio.sleep(1.0)
