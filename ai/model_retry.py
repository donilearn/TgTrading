import logging
import time

from google.genai import errors

from ai.network_retry import is_retryable_network_error

logger = logging.getLogger(__name__)

RETRYABLE_CODES = {429, 500, 503, 504}
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0


def generate_with_fallback(
    client,
    primary_model: str,
    fallback_models: list[str],
    contents,
    config,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
):
    models = [primary_model] + [
        model for model in fallback_models if model != primary_model
    ]
    last_error: Exception | None = None

    for model in models:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                if model != primary_model:
                    logger.warning("Primary model unavailable, used fallback: %s", model)
                else:
                    logger.info("Gemini response OK model=%s", model)
                return response

            except errors.APIError as exc:
                last_error = exc
                if exc.code not in RETRYABLE_CODES:
                    raise

            except Exception as exc:
                last_error = exc
                if not is_retryable_network_error(exc):
                    raise
                logger.warning(
                    "Gemini %s network error: %s",
                    model,
                    exc,
                )

            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Gemini %s retry %d/%d in %.1fs (%s)",
                    model,
                    attempt + 1,
                    max_retries,
                    delay,
                    last_error,
                )
                time.sleep(delay)
                continue

            if isinstance(last_error, errors.APIError):
                logger.warning(
                    "Gemini %s unavailable after %d retries (%s), trying next model",
                    model,
                    max_retries,
                    last_error.code,
                )
            else:
                logger.warning(
                    "Gemini %s network failed after %d retries, trying next model",
                    model,
                    max_retries,
                )
            break

    if last_error:
        raise last_error

    raise RuntimeError("No Gemini models configured")
