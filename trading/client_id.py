import secrets
import string

from trading.order_comment_builder import MAX_ORDER_COMMENT_LEN, build_order_comment

STRATEGY_ID = "TG"
MAX_CLIENT_ID_LEN = 26


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
    channel_name: str,
    message_date: str | None,
    is_re_entry: bool = False,
) -> dict:
    del is_re_entry
    comment = build_order_comment(channel_name, message_date)
    client_id = build_client_id(symbol, order_index)
    if len(client_id) > MAX_CLIENT_ID_LEN:
        client_id = client_id[:MAX_CLIENT_ID_LEN]
    if len(comment) > MAX_ORDER_COMMENT_LEN:
        comment = comment[:MAX_ORDER_COMMENT_LEN]

    return {
        "comment": comment,
        "clientId": client_id,
        "magic": magic,
    }
