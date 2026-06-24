import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_HINTS = (
    "timed out",
    "timeout",
    "not connected",
    "connection closed",
    "disconnected",
    "not connected to broker",
    "not synchronized",
)


def is_retryable_trade_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(hint in text for hint in _RETRYABLE_HINTS)


async def run_trade_with_retry(
    metaapi: Any,
    operation: Callable[[Any], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await metaapi.run_rpc(operation)
        except Exception as exc:
            last_error = exc
            if not is_retryable_trade_error(exc) or attempt >= max_retries - 1:
                raise

            logger.warning(
                "Trade timeout/error, retry %d/%d: %s",
                attempt + 1,
                max_retries,
                exc,
            )
            metaapi.request_reconnect()
            await metaapi.ensure_rpc_ready()
            await asyncio.sleep(base_delay * (attempt + 1))

    if last_error:
        raise last_error
    raise RuntimeError("Trade retry failed")
