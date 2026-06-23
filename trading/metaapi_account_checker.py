import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEPLOYED_STATES = frozenset({"DEPLOYED", "DEPLOYING"})
_CONNECTED_STATES = frozenset({"CONNECTED", "CONNECTING"})


async def ensure_account_ready(account: Any) -> None:
    """Account DEPLOYED va broker CONNECTED bo'lguncha kutadi."""
    state = _normalize_state(getattr(account, "state", None))
    connection_status = _normalize_state(getattr(account, "connection_status", None))

    if state not in _DEPLOYED_STATES:
        logger.info("MetaAPI account state=%s — deploying", state or "unknown")
        await account.deploy()

    wait_deployed = getattr(account, "wait_deployed", None)
    if callable(wait_deployed):
        await wait_deployed()

    if connection_status not in _CONNECTED_STATES:
        logger.info(
            "MetaAPI account connection_status=%s — waiting for broker",
            connection_status or "unknown",
        )

    await account.wait_connected()
    logger.info(
        "MetaAPI account ready: state=%s connection_status=%s",
        _normalize_state(getattr(account, "state", None)),
        _normalize_state(getattr(account, "connection_status", None)),
    )


def _normalize_state(value: Any) -> str:
    if value is None:
        return ""
    return str(value).upper()
