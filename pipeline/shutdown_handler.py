import asyncio
import logging
import signal

logger = logging.getLogger(__name__)


class ShutdownHandler:
    """Cooperative shutdown on SIGINT/SIGTERM instead of abrupt task cancellation."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def register(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._on_signal)

    def _on_signal(self) -> None:
        if not self._event.is_set():
            logger.info("Shutdown signal received")
            self._event.set()

    async def wait(self) -> None:
        await self._event.wait()
