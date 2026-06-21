import secrets
import string

STRATEGY_ID = "TG"
MAX_COMMENT_CLIENT_LEN = 26


def build_client_id(symbol: str, order_index: int) -> str:
    symbol_part = "".join(c for c in symbol.upper() if c.isalnum())[:10]
    suffix = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(6)
    )
    order_id = f"{order_index}{suffix}"
    return f"{STRATEGY_ID}_{symbol_part}_{order_id}"


def build_trade_options(
    symbol: str,
    order_index: int,
    magic: int,
    is_re_entry: bool = False,
) -> dict:
    comment = "re" if is_re_entry else "tg"
    client_id = build_client_id(symbol, order_index)

    max_client_len = MAX_COMMENT_CLIENT_LEN - len(comment)
    if len(client_id) > max_client_len:
        client_id = client_id[:max_client_len]

    return {
        "comment": comment,
        "clientId": client_id,
        "magic": magic,
    }
