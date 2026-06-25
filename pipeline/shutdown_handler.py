import asyncio
import logging
import signal
import sys

logger = logging.getLogger(__name__)


class ShutdownHandler:
    """Cooperative shutdown on SIGINT/SIGTERM instead of abrupt task cancellation."""

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._signal_count = 0

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def register(self) -> None:
        if sys.platform == "win32":
            signal.signal(signal.SIGINT, self._win_signal_handler)
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, self._win_signal_handler)
            return

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._on_signal)

    def _win_signal_handler(self, signum: int, frame) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._on_signal)
        except RuntimeError:
            self._on_signal()

    def _on_signal(self) -> None:
        self._signal_count += 1
        if self._signal_count > 1:
            logger.warning("Forced shutdown (signal received again)")
            raise SystemExit(1)
        if not self._event.is_set():
            logger.info("Shutdown signal received")
            self._event.set()

    async def wait(self) -> None:
        await self._event.wait()
