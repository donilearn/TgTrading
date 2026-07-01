import re

from ai.short_price_resolver import resolve_short_price

_SL_PRICE_LINE = re.compile(
    r"^\s*(?:[^\w]*\s*)?(?:SL|stop\s*loss)\s*:?\s*(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_sl_level(
    text: str | None,
    reference_price: float | None = None,
) -> float | None:
    """Xabardan SL narxini qaytaradi (masalan ❌SL 4035)."""
    if not text:
        return None

    for match in _SL_PRICE_LINE.finditer(text):
        return resolve_short_price(float(match.group(1)), reference_price)

    return None
