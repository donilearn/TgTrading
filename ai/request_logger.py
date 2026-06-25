import json
import logging

logger = logging.getLogger(__name__)

_MAX_LOG_CHARS = 6000


def summarize_payload(payload) -> str:
    if isinstance(payload, str):
        body = payload
    elif isinstance(payload, list):
        lines: list[str] = []
        for item in payload:
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
            if isinstance(item, dict):
                lines.append(json.dumps(item, ensure_ascii=False)[:500])
            else:
                lines.append(repr(item))
        body = "\n---\n".join(lines)
    else:
        body = repr(payload)

    if len(body) <= _MAX_LOG_CHARS:
        return body
    return f"{body[:_MAX_LOG_CHARS]}...(truncated)"


def log_ai_request(
    chat_id: int,
    provider: str,
    model: str,
    payload,
    system_prompt_chars: int,
) -> None:
    logger.info(
        "AI REQUEST chat=%s provider=%s model=%s prompt_chars=%d\n%s",
        chat_id,
        provider,
        model,
        system_prompt_chars,
        summarize_payload(payload),
    )


def log_ai_response(chat_id: int, provider: str, model: str, response) -> None:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        try:
            body = parsed.model_dump_json()
        except Exception:
            body = str(parsed)
    elif hasattr(response, "model_dump_json"):
        body = response.model_dump_json()
    else:
        body = getattr(response, "text", None) or repr(response)

    if len(body) > _MAX_LOG_CHARS:
        body = f"{body[:_MAX_LOG_CHARS]}...(truncated)"

    logger.info(
        "AI RESPONSE chat=%s provider=%s model=%s\n%s",
        chat_id,
        provider,
        model,
        body,
    )


def log_ai_error(chat_id: int, provider: str, model: str, exc: Exception) -> None:
    logger.error(
        "AI ERROR chat=%s provider=%s model=%s: %s",
        chat_id,
        provider,
        model,
        exc,
    )


# Eski nomlar — backward compat
log_gemini_request = log_ai_request
log_gemini_response = log_ai_response
log_gemini_error = log_ai_error
summarize_contents = summarize_payload
