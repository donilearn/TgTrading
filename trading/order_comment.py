from datetime import UTC, datetime

# XM va ko'p brokerlar order_send da 31 emas, 29 belgigacha qabul qiladi
MT5_COMMENT_MAX_LEN = 29
_TIME_FMT = "%H-%M"


def sanitize_mt5_comment(text: str, *, fallback: str = "TG") -> str:
    """MT5 order_send uchun xavfsiz comment (uzunlik + belgilar)."""
    cleaned = text.replace(":", " ").replace(";", " ")
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        cleaned = fallback
    return cleaned[:MT5_COMMENT_MAX_LEN]


def build_order_comment(channel_name: str, message_time: str | None = None) -> str:
    """MT5 order comment: mahalliy vaqt (HH-MM) + kanal nomi."""
    time_label = _extract_time_label(message_time) or _local_now_label()
    name = _sanitize_channel_name(channel_name)
    prefix = f"{time_label} "
    max_name_len = MT5_COMMENT_MAX_LEN - len(prefix)
    if max_name_len < 1:
        return sanitize_mt5_comment(time_label)
    if len(name) > max_name_len:
        name = name[:max_name_len].rstrip()
    return sanitize_mt5_comment(f"{prefix}{name}")


def _extract_time_label(message_time: str | datetime | None) -> str | None:
    if message_time is None:
        return None

    if isinstance(message_time, datetime):
        parsed = message_time
    else:
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

    try:
        parsed_time = datetime.strptime(text, "%H:%M")
    except ValueError:
        return None

    today = datetime.now().astimezone()
    return parsed_time.replace(
        year=today.year,
        month=today.month,
        day=today.day,
        tzinfo=today.tzinfo,
    )


def _local_now_label() -> str:
    return datetime.now().astimezone().strftime(_TIME_FMT)


def _sanitize_channel_name(channel_name: str) -> str:
    # MT5 commentda : ; va boshqa belgilar muammo qiladi
    cleaned = channel_name.replace(":", " ").replace(";", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned or "TG"
