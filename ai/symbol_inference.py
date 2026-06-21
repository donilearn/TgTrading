from trading.symbol_validator import resolve_env_symbol, symbol_match_key

KEYWORD_TO_SYMBOL_PART = {
    "btc": "BTC",
    "bitcoin": "BTC",
    "eth": "ETH",
    "ethereum": "ETH",
    "gold": "XAU",
    "xau": "XAU",
    "eurusd": "EURUSD",
    "gbpusd": "GBPUSD",
}


def infer_symbol_from_context(
    context_messages: list,
    allowed_symbols: list[str],
) -> str | None:
    """Find symbol from recent context (most recent message first)."""
    for msg in reversed(context_messages):
        text = getattr(msg, "text", None) or ""
        resolved = infer_symbol(None, text, allowed_symbols, None)
        if resolved:
            return resolved
    return None


def infer_symbol(
    detected_symbol: str | None,
    message_text: str,
    allowed_symbols: list[str],
    default_symbol: str | None = None,
) -> str | None:
    if detected_symbol:
        return resolve_env_symbol(detected_symbol, allowed_symbols)

    if not allowed_symbols:
        return None

    text = message_text.lower()

    for env_symbol in allowed_symbols:
        if env_symbol.lower() in text:
            return env_symbol

    for keyword, part in KEYWORD_TO_SYMBOL_PART.items():
        if keyword in text:
            for env_symbol in allowed_symbols:
                if part in symbol_match_key(env_symbol):
                    return env_symbol

    if default_symbol:
        resolved = resolve_env_symbol(default_symbol, allowed_symbols)
        if resolved:
            return resolved

    if len(allowed_symbols) == 1:
        return allowed_symbols[0]

    return None
