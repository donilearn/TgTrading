import asyncio
import contextlib
import logging

from trading.client import MetaApiService

logger = logging.getLogger(__name__)

_KEEPER_INTERVAL_SEC = 60.0
_UNHEALTHY_LOG_INTERVAL_SEC = 120.0
_CONNECT_GRACE_SEC = 90.0


class MetaApiConnectionKeeper:
    """Fon rejimida MetaAPI ulanishini sog'lom tutadi — xabar kelguncha kutmaydi."""

    def __init__(self, service: MetaApiService) -> None:
        self._service = service
        self._task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_unhealthy_log = 0.0

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(
            self._run_loop(),
            name="metaapi-connection-keeper",
        )
        logger.info("MetaAPI connection keeper started (interval=%ss)", _KEEPER_INTERVAL_SEC)

    async def stop(self) -> None:
        self._stop.set()
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("MetaAPI connection keeper stopped")

    def request_reconnect(self) -> None:
        self._service.request_reconnect()
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(
            self._service.reconnect_all(),
            name="metaapi-immediate-reconnect",
        )

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=_KEEPER_INTERVAL_SEC,
                )
                break
            except TimeoutError:
                pass

            if self._stop.is_set():
                break

            if self._in_connect_grace():
                continue

            if self._service.reconnect_pending:
                await self._service.reconnect_all()
                continue

            healthy = await self._service.check_health()
            if healthy:
                continue

            now = asyncio.get_running_loop().time()
            if now - self._last_unhealthy_log >= _UNHEALTHY_LOG_INTERVAL_SEC:
                logger.warning("MetaAPI unhealthy — proactive reconnect")
                self._last_unhealthy_log = now
            await self._service.reconnect_all()

    def _in_connect_grace(self) -> bool:
        last_connect = self._service.last_connect_at
        if last_connect <= 0:
            return False
        elapsed = asyncio.get_running_loop().time() - last_connect
        return elapsed < _CONNECT_GRACE_SEC
