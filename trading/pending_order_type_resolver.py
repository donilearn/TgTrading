def resolve_pending_order_type(
    side: str,
    entry_price: float,
    bid: float | None,
    ask: float | None,
) -> str:
    """
    MT5 pending order turi:
    Buy LIMIT: price < ask | Buy STOP: price > ask
    Sell LIMIT: price > bid | Sell STOP: price < bid
    """
    side_lower = side.lower()
    if side_lower == "buy":
        reference = ask if ask is not None else bid
        if reference is None:
            return "limit"
        return "limit" if entry_price < reference else "stop"

    if side_lower == "sell":
        reference = bid if bid is not None else ask
        if reference is None:
            return "limit"
        return "limit" if entry_price > reference else "stop"

    return "limit"
