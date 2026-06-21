def symbol_match_key(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace(" ", "")


def resolve_env_symbol(symbol: str, allowed_symbols: list[str]) -> str | None:
    """Map detected symbol to exact .env value (case-sensitive broker format)."""
    if not symbol:
        return None
    if not allowed_symbols:
        return symbol

    key = symbol_match_key(symbol)
    for env_symbol in allowed_symbols:
        if symbol_match_key(env_symbol) == key:
            return env_symbol

    return None


def is_symbol_allowed(symbol: str, allowed_symbols: list[str]) -> bool:
    return resolve_env_symbol(symbol, allowed_symbols) is not None
