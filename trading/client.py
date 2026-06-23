import asyncio
import logging

from metaapi_cloud_sdk import MetaApi

from config.settings import Settings

logger = logging.getLogger(__name__)

_RECONNECT_SETTLE_SEC = 2.0
_HEALTH_CHECK_TIMEOUT = 30.0


def _is_rate_limited(exc: Exception) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return "toomanyrequests" in name.lower() or "too many" in text


class MetaApiService:
    def __init__(self, settings: Settings) -> None:
        self._api = MetaApi(token=settings.metaapi_token)
        self._account_id = settings.metaapi_account_id
        self._connection = None
        self._connected = False
        self._op_lock = asyncio.Lock()

    @property
    def api(self) -> MetaApi:
        return self._api

    @property
    def connection(self):
        if self._connection is None:
            raise RuntimeError("MetaAPI connection is not established")
        return self._connection

    async def connect(self) -> None:
        async with self._op_lock:
            if self._connected and self._connection is not None:
                return
            await self._connect_inner()

    async def ensure_ready(self) -> None:
        async with self._op_lock:
            if not self._connected or self._connection is None:
                await self._connect_inner()
                return

            try:
                await asyncio.wait_for(
                    self._connection.get_account_information(),
                    timeout=_HEALTH_CHECK_TIMEOUT,
                )
            except Exception as exc:
                if _is_rate_limited(exc):
                    logger.warning(
                        "MetaAPI rate limited on health check, waiting %.0fs",
                        _RECONNECT_SETTLE_SEC,
                    )
                    await asyncio.sleep(_RECONNECT_SETTLE_SEC)
                    return
                logger.warning("MetaAPI RPC stale, reconnecting: %s", exc)
                await self._reconnect_rpc_inner()

    async def recover_after_timeout(self) -> None:
        async with self._op_lock:
            logger.warning("MetaAPI recover after timeout — waiting %.0fs", _RECONNECT_SETTLE_SEC)
            await asyncio.sleep(_RECONNECT_SETTLE_SEC)
            try:
                await self._reconnect_rpc_inner()
            except Exception as exc:
                if not _is_rate_limited(exc):
                    raise
                logger.warning(
                    "MetaAPI still rate limited, retry RPC reconnect in %.0fs",
                    _RECONNECT_SETTLE_SEC * 2,
                )
                await asyncio.sleep(_RECONNECT_SETTLE_SEC * 2)
                await self._reconnect_rpc_inner()

    async def reconnect_rpc(self) -> None:
        async with self._op_lock:
            await self._reconnect_rpc_inner()

    async def disconnect(self) -> None:
        async with self._op_lock:
            if not self._connected and self._connection is None:
                return

            connection = self._connection
            self._connection = None
            self._connected = False

            if connection is not None:
                await self._close_rpc_connection(connection)
                await asyncio.sleep(0.3)

            await self._close_websocket_client()
            logger.info("MetaAPI disconnected")

    async def _connect_inner(self) -> None:
        account = await self._api.metatrader_account_api.get_account(
            self._account_id,
        )
        await account.deploy()
        await account.wait_connected()

        self._connection = account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized()
        self._connected = True
        await asyncio.sleep(_RECONNECT_SETTLE_SEC)
        logger.info("MetaAPI connected to account %s", self._account_id)

    async def _reconnect_rpc_inner(self) -> None:
        if self._connection is not None:
            old = self._connection
            self._connection = None
            await self._close_rpc_connection(old)
            await asyncio.sleep(_RECONNECT_SETTLE_SEC)

        account = await self._api.metatrader_account_api.get_account(
            self._account_id,
        )
        await account.wait_connected()

        self._connection = account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized()
        self._connected = True
        logger.info("MetaAPI RPC reconnected")

    async def _close_rpc_connection(self, connection) -> None:
        """SDK RpcMetaApiConnectionInstance.close() schedules work in background."""
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
        """SDK MetaApi.close() does not await websocket — close explicitly."""
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
