import argparse
import asyncio
import logging

from config.backend_validation import validate_backend_settings
from config.logging_setup import setup_logging
from config.settings import get_settings
from pipeline.orchestrator import TradingPipeline

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TgTrading copy-trading bot")
    parser.add_argument(
        "--win",
        action="store_true",
        help="Windows local MT5 API (terminal ochiq). Default: MetaAPI cloud.",
    )
    return parser.parse_args()


def _asyncio_exception_handler(_loop, context: dict) -> None:
    exc = context.get("exception")
    if exc is not None:
        logger.error("Background task error: %s", exc, exc_info=exc)
        return
    logger.error("Background task error: %s", context.get("message"))


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    setup_logging(
        log_dir=settings.log_dir,
        retention_days=settings.log_retention_days,
        console=settings.log_to_console,
        file_logging=settings.log_to_file,
    )
    validate_backend_settings(settings, win_mode=args.win)

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_asyncio_exception_handler)
    pipeline = TradingPipeline(settings, win_mode=args.win)
    await pipeline.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
