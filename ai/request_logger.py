import json
import logging

logger = logging.getLogger(__name__)

_MAX_LOG_CHARS = 6000


def summarize_contents(contents) -> str:
    lines: list[str] = []
    for item in contents:
        text = getattr(item, "text", None)
        if text:
            lines.append(text)
            continue

        inline = getattr(item, "inline_data", None)
        if inline is not None:
            data = getattr(inline, "data", b"") or b""
            mime = getattr(inline, "mime_type", "unknown")
            lines.append(f"[media mime={mime} bytes={len(data)}]")
            continue

        lines.append(repr(item))

    body = "\n---\n".join(lines)
    if len(body) <= _MAX_LOG_CHARS:
        return body
    return f"{body[:_MAX_LOG_CHARS]}...(truncated)"


def log_gemini_request(
    chat_id: int,
    model: str,
    contents,
    system_prompt_chars: int,
) -> None:
    logger.info(
        "AI REQUEST chat=%s model=%s prompt_chars=%d\n%s",
        chat_id,
        model,
        system_prompt_chars,
        summarize_contents(contents),
    )


def log_gemini_response(chat_id: int, model: str, response) -> None:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        try:
            body = parsed.model_dump_json()
        except Exception:
            body = str(parsed)
    else:
        body = getattr(response, "text", None) or repr(response)

    if len(body) > _MAX_LOG_CHARS:
        body = f"{body[:_MAX_LOG_CHARS]}...(truncated)"

    logger.info("AI RESPONSE chat=%s model=%s\n%s", chat_id, model, body)


def log_gemini_error(chat_id: int, model: str, exc: Exception) -> None:
    logger.error("AI ERROR chat=%s model=%s: %s", chat_id, model, exc)
