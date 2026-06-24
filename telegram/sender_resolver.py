from typing import Any


def resolve_sender(entity: Any | None) -> tuple[str, int | None, str | None]:
    """username/id, sender_id, display_name qaytaradi."""
    if entity is None:
        return "unknown", None, None

    sender_id = getattr(entity, "id", None)
    username = getattr(entity, "username", None)
    first_name = getattr(entity, "first_name", None)
    last_name = getattr(entity, "last_name", None)
    title = getattr(entity, "title", None)

    display_parts = [part for part in (first_name, last_name) if part]
    display_name = " ".join(display_parts) if display_parts else title

    if username:
        sender = f"@{username}"
    elif sender_id is not None:
        sender = str(sender_id)
    else:
        sender = "unknown"

    return sender, sender_id, display_name
