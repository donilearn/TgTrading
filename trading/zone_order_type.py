from models.order_type import OrderType


def resolve_zone_order_type(signal_order_type: OrderType) -> OrderType:
    """Zone entries are always pending orders across the range."""
    if signal_order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
        return signal_order_type
    return OrderType.LIMIT
