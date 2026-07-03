import re

from ai.close_all_detector import message_asks_close_all

# Broker kontekstsiz LLM bu xabarlarni noto'g'ri is_signal=false deb qaytaradi.
_PROFIT_UPDATE = re.compile(
    r"\d+\s*pips?\s*(\+\+|✅|hit|done|reached)?",
    re.IGNORECASE,
)
_MANAGEMENT_PHRASES = (
    "manage profit",
    "running profit",
    "hit tp",
    "tp1 hit",
    "tp2 hit",
    "tp3 hit",
    "tp hit",
    "secure half",
    "secure the",
    "secure profit",
    "set be",
    "set breakeven",
    "breakeven",
    "break even",
    "half close",
    "half then",
    "yarmini yop",
    "qisman yop",
    "partial close",
    "partial save",
    "save half",
    "50% close",
    "50% save",
    "close half",
    "sl hit",
    "stopped out",
    "tp done",
)


def message_needs_broker_context(text: str | None) -> bool:
    """MetaAPI order snapshot talab qiladigan management xabarlar."""
    if not text or not text.strip():
        return False

    if message_asks_close_all(text):
        return True

    lower = text.lower()
    if _PROFIT_UPDATE.search(lower):
        return True

    return any(phrase in lower for phrase in _MANAGEMENT_PHRASES)
