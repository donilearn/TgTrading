def format_trade_error(api, exc: Exception) -> str:
    formatted = api.format_error(exc)

    if isinstance(formatted, dict):
        message = formatted.get("message", "Trade error")
        details = formatted.get("details", [])
        if details:
            parts = [
                f"{d.get('parameter', '?')}: {d.get('message', d)}"
                for d in details
            ]
            return f"{message} — {', '.join(parts)}"
        return message

    return str(formatted)
