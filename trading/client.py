import asyncio
import logging

from metaapi_cloud_sdk import MetaApi

from config.settings import Settings

logger = logging.getLogger(__name__)


class MetaApiService:
    def __init__(self, settings: Settings) -> None:
        self._api = MetaApi(token=settings.metaapi_token)
        self._account_id = settings.metaapi_account_id
        self._connection = None
        self._connected = False

    @property
    def api(self) -> MetaApi:
        return self._api

    @property
    def connection(self):
        if self._connection is None:
            raise RuntimeError("MetaAPI connection is not established")
        return self._connection

    async def connect(self) -> None:
        account = await self._api.metatrader_account_api.get_account(
            self._account_id,
        )
        await account.deploy()
        await account.wait_connected()

        self._connection = account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized()
        self._connected = True
        logger.info("MetaAPI connected to account %s", self._account_id)

    async def ensure_ready(self) -> None:
        if not self._connected or self._connection is None:
            await self.connect()
            return

        try:
            await self._connection.get_account_information()
        except Exception:
            logger.warning("MetaAPI RPC stale, reconnecting...")
            await self.reconnect_rpc()

    async def reconnect_rpc(self) -> None:
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception as exc:
                logger.debug("RPC close before reconnect: %s", exc)
            self._connection = None

        account = await self._api.metatrader_account_api.get_account(
            self._account_id,
        )
        await account.wait_connected()

        self._connection = account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized()
        self._connected = True
        logger.info("MetaAPI RPC reconnected")

    async def disconnect(self) -> None:
        if not self._connected and self._connection is None:
            return

        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception as exc:
                logger.debug("MetaAPI RPC close: %s", exc)
            self._connection = None

        await self._close_websocket_client()
        self._connected = False
        logger.info("MetaAPI disconnected")

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
