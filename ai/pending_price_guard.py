from models.existing_order import ExistingOrder


def has_pending_near_price(
    existing: list[ExistingOrder],
    symbol: str,
    side: str,
    price: float,
    tolerance: float = 0.5,
) -> bool:
    """Shu narx atrofida allaqachon pending limit/stop bormi."""
    for item in existing:
        if item.is_position:
            continue
        if item.symbol != symbol:
            continue
        if item.side.lower() != side.lower():
            continue
        if abs(item.open_price - price) <= tolerance:
            return True
    return False
