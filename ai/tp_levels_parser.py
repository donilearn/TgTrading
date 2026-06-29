import re

from ai.short_price_resolver import resolve_short_price

_SUPERSCRIPT_LEVELS = {
    "¹": 1, "²": 2, "³": 3, "⁴": 4, "⁵": 5,
    "⁶": 6, "⁷": 7, "⁸": 8, "⁹": 9,
}
_TP_SUPER = re.compile(
    r"TP\s*([¹²³⁴⁵⁶⁷⁸⁹])\s*:?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
# TP1: 4033 yoki TP1 4033 (level + narx)
_TP_LEVEL_PRICE = re.compile(
    r"\bTP\s*(\d{1,2})\s*(?:[:：]\s*|\s+)(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
# Har bir qator: "Tp 4033" (faqat narx, level yo'q)
_TP_PRICE_LINE = re.compile(
    r"^\s*(?:TP|take\s*profit)\s*:?\s*(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_tp_levels(
    text: str | None,
    reference_price: float | None = None,
) -> list[float]:
    """Xabardan TP narxlarini tartib bilan qaytaradi."""
    if not text:
        return []

    line_prices = _parse_tp_price_lines(text, reference_price)
    if line_prices:
        return line_prices

    indexed: dict[int, float] = {}

    for match in _TP_SUPER.finditer(text):
        level = _SUPERSCRIPT_LEVELS[match.group(1)]
        price = resolve_short_price(float(match.group(2)), reference_price)
        indexed[level] = price

    for match in _TP_LEVEL_PRICE.finditer(text):
        level = int(match.group(1))
        price = resolve_short_price(float(match.group(2)), reference_price)
        indexed[level] = price

    if not indexed:
        return []

    return [indexed[level] for level in sorted(indexed)]


def _parse_tp_price_lines(
    text: str,
    reference_price: float | None,
) -> list[float]:
    prices: list[float] = []
    for match in _TP_PRICE_LINE.finditer(text):
        price = resolve_short_price(float(match.group(1)), reference_price)
        prices.append(price)
    return prices
