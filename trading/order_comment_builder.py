import re
from datetime import UTC, datetime

MAX_ORDER_COMMENT_LEN = 31


def build_order_comment(channel_name: str, message_date: str | None) -> str:
    """Build MT comment: channel name + message time as HHMM only."""
    hhmm = _extract_hhmm(message_date)
    safe_name = _sanitize_channel_name(channel_name)
    max_name_len = MAX_ORDER_COMMENT_LEN - len(hhmm)
    if max_name_len < 1:
        return hhmm[:MAX_ORDER_COMMENT_LEN]
    return f"{safe_name[:max_name_len]}{hhmm}"


def _sanitize_channel_name(name: str) -> str:
    cleaned = re.sub(r"[^\w]", "", name, flags=re.UNICODE)
    return cleaned or "channel"


def _extract_hhmm(message_date: str | None) -> str:
    if not message_date:
        return datetime.now(UTC).strftime("%H%M")
    try:
        dt = datetime.fromisoformat(message_date.replace("Z", "+00:00"))
        return dt.strftime("%H%M")
    except ValueError:
        return "0000"
