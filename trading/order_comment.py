from datetime import UTC, datetime

MT5_COMMENT_MAX_LEN = 31
# MT5 ko'p brokerlarda ':' dan keyingi qismni kesadi — HHMM ishlatamiz (masalan 0531)
_TIME_FMT = "%H%M"


def build_order_comment(channel_name: str, message_time: str | None = None) -> str:
    """MT5 order comment: kanal nomi + mahalliy vaqt (HHMM)."""
    time_label = _extract_time_label(message_time) or _local_now_label()
    name = _sanitize_channel_name(channel_name)
    suffix = f" {time_label}"
    max_name_len = MT5_COMMENT_MAX_LEN - len(suffix)
    if max_name_len < 1:
        return time_label[:MT5_COMMENT_MAX_LEN]
    if len(name) > max_name_len:
        name = name[:max_name_len].rstrip()
    return f"{name}{suffix}"


def _extract_time_label(message_time: str | None) -> str | None:
    if not message_time:
        return None

    parsed = _parse_datetime(message_time)
    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone().strftime(_TIME_FMT)


def _parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def _local_now_label() -> str:
    return datetime.now().astimezone().strftime(_TIME_FMT)


def _sanitize_channel_name(channel_name: str) -> str:
    # MT5 commentda : ; va boshqa belgilar muammo qiladi
    cleaned = channel_name.replace(":", " ").replace(";", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned or "TG"
