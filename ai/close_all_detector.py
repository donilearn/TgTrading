import re

# Guruh bo'yicha barcha pozitsiya + pending yopish/cancel
_CLOSE_ALL_PHRASES = re.compile(
    r"\b("
    r"yoping|yopish|yopamiz|yop|"
    r"close\s+all|close\s+everything|close\s+all\s+trade?s?|close\s+position?s?|"
    r"hammasini\s+yop|barchasini\s+yop|hamma\s+yop|hamma\s+trade\s+yop|"
    r"exit\s+all|kill\s+all|stop\s+all\s+trade?s?|"
    r"cancel\s+all\s+trade?s?|cancel\s+(the\s+)?signal|signal\s+cancel(?:led|ed)?|"
    r"invalid\s+signal|signal\s+invalid|"
    r"flatten|all\s+out|square\s+off"
    r")\b",
    re.IGNORECASE,
)

_STANDALONE_CLOSE = re.compile(
    r"^(yoping|yopish|yop|close\s+all|exit|flatten)\s*[!.✅🔥]*\s*$",
    re.IGNORECASE,
)

# Qisqa buyruq + emoji (masalan "YOPING 🔥", "close all ✅")
_CLOSE_ALL_PREFIX = re.compile(
    r"^(yoping|yopish|yop|close\s+all|hammasini\s+yop|exit\s+all|flatten)\b",
    re.IGNORECASE,
)


def message_asks_close_all(message_text: str | None) -> bool:
    """Guruh bo'yicha barcha pozitsiya + pending yopish/cancel buyrug'i."""
    if not message_text or not message_text.strip():
        return False

    stripped = message_text.strip()
    if _STANDALONE_CLOSE.match(stripped):
        return True
    if _CLOSE_ALL_PHRASES.search(stripped):
        return True
    if _CLOSE_ALL_PREFIX.match(stripped):
        return True
    return False
