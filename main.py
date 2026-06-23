import asyncio
import logging
import sys

from config.settings import get_settings
from pipeline.orchestrator import TradingPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logging.getLogger("engineio.client").setLevel(logging.ERROR)
logging.getLogger("socketio.client").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai.models").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _asyncio_exception_handler(_loop, context: dict) -> None:
    exc = context.get("exception")
    if exc is not None:
        logger.error("Background task error: %s", exc, exc_info=exc)
        return
    logger.error("Background task error: %s", context.get("message"))


async def main() -> None:
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_asyncio_exception_handler)
    settings = get_settings()
    pipeline = TradingPipeline(settings)
    await pipeline.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
