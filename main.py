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


async def main() -> None:
    settings = get_settings()
    pipeline = TradingPipeline(settings)
    await pipeline.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
