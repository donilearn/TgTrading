from trading.order_comment import build_order_comment


def build_trade_options(
    magic: int,
    channel_name: str,
    message_time: str | None = None,
) -> dict:
    return {
        "comment": build_order_comment(
            channel_name,
            message_time,
            fallback_label=f"G{magic}",
        ),
        "magic": magic,
    }
