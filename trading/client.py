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


def _is_rate_limited(exc: Exception) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return "toomanyrequests" in name.lower() or "too many" in text


class MetaApiService:
    """Bitta uzoq muddatli RPC connection — har requestda yangi connect qilmaydi."""

    def __init__(self, settings: Settings) -> None:
        self._api = MetaApi(token=settings.metaapi_token)
        self._account_id = settings.metaapi_account_id
        self._account = None
        self._connection = None
        self._connected = False
        self._lifecycle_lock = asyncio.Lock()
        self._rpc_lock = asyncio.Lock()

    @property
    def api(self) -> MetaApi:
        return self._api

    @property
    def connection(self):
        if self._connection is None:
            raise RuntimeError("MetaAPI connection is not established")
        return self._connection

    async def connect(self) -> None:
        async with self._lifecycle_lock:
            if self._connected and self._connection is not None:
                return
            await self._connect_inner()

    async def ensure_ready(self) -> None:
        """Servis qatlamida connection borligini tekshiradi — har trade oldidan emas."""
        async with self._lifecycle_lock:
            if self._connected and self._connection is not None:
                return
            await self._connect_inner()

    async def run_rpc(
        self,
        operation: Callable[[Any], Awaitable[T]],
    ) -> T:
        """Barcha MetaAPI RPC chaqiruvlari serial lock ostida."""
        await self.ensure_ready()
        async with self._rpc_lock:
            return await operation(self.connection)

    async def recover_after_timeout(self) -> None:
        async with self._lifecycle_lock:
            async with self._rpc_lock:
                logger.warning(
                    "MetaAPI recover after timeout — waiting %.0fs",
                    _RECONNECT_SETTLE_SEC,
                )
                await asyncio.sleep(_RECONNECT_SETTLE_SEC)
                try:
                    await self._reconnect_rpc_inner_unlocked()
                except Exception as exc:
                    if not _is_rate_limited(exc):
                        raise
                    logger.warning(
                        "MetaAPI still rate limited, retry RPC reconnect in %.0fs",
                        _RECONNECT_SETTLE_SEC * 2,
                    )
                    await asyncio.sleep(_RECONNECT_SETTLE_SEC * 2)
                    await self._reconnect_rpc_inner_unlocked()

    async def reconnect_rpc(self) -> None:
        async with self._lifecycle_lock:
            async with self._rpc_lock:
                await self._reconnect_rpc_inner_unlocked()

    async def disconnect(self) -> None:
        async with self._lifecycle_lock:
            async with self._rpc_lock:
                if not self._connected and self._connection is None:
                    return

                connection = self._connection
                self._connection = None
                self._connected = False
                self._account = None

                if connection is not None:
                    await self._close_rpc_connection(connection)
                    await asyncio.sleep(0.3)

            await self._close_websocket_client()
            logger.info("MetaAPI disconnected")

    async def _connect_inner(self) -> None:
        account = await self._api.metatrader_account_api.get_account(
            self._account_id,
        )
        await ensure_account_ready(account)

        self._account = account
        self._connection = account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized()
        self._connected = True
        await asyncio.sleep(_RECONNECT_SETTLE_SEC)
        logger.info("MetaAPI connected to account %s", self._account_id)

    async def _reconnect_rpc_inner_unlocked(self) -> None:
        """lifecycle + rpc lock allaqachon olingan bo'lishi kerak."""
        if self._connection is not None:
            old = self._connection
            self._connection = None
            self._connected = False
            await self._close_rpc_connection(old)
            await asyncio.sleep(_RECONNECT_SETTLE_SEC)

        account = self._account
        if account is None:
            account = await self._api.metatrader_account_api.get_account(
                self._account_id,
            )
            self._account = account

        await account.wait_connected()

        self._connection = account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized()
        self._connected = True
        logger.info("MetaAPI RPC reconnected")

    async def _close_rpc_connection(self, connection) -> None:
        try:
            if getattr(connection, "_closed", False):
                return
            inner = connection._meta_api_connection
            await inner.close(connection.instance_id)
            connection._closed = True
        except KeyError:
            pass
        except Exception as exc:
            logger.debug("MetaAPI RPC close: %s", exc)

    async def _close_websocket_client(self) -> None:
        try:
            ws_client = self._api._metaapi_websocket_client
            await ws_client.close()
            ws_client.stop()
        except Exception as exc:
            logger.debug("MetaAPI websocket close: %s", exc)

        try:
            self._api._terminal_hash_manager._stop()
        except Exception:
            pass

        await asyncio.sleep(0.5)
