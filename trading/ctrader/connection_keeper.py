import asyncio
import contextlib
import logging

from trading.ctrader.service import CTraderService

logger = logging.getLogger(__name__)

_KEEPER_INTERVAL_SEC = 60.0


class CTraderConnectionKeeper:
    """Ulanish sog'ligini tekshiradi — reconnect kerak bo'lsa."""

    def __init__(self, service: CTraderService) -> None:
        self._service = service
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(
            self._run_loop(),
            name="ctrader-connection-keeper",
        )
        logger.info("cTrader connection keeper started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=_KEEPER_INTERVAL_SEC)
                break
            except TimeoutError:
                pass

            if self._stop.is_set():
                break

            if self._service.is_ready:
                continue

            logger.warning("cTrader session unhealthy — reconnecting")
            try:
                await self._service.reconnect_all()
            except Exception as exc:
                logger.error("cTrader reconnect failed: %s", exc)
