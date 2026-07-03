from datetime import UTC, datetime, timedelta

from models.order_type import OrderType

_EXPIRATION_TYPE = "ORDER_TIME_SPECIFIED"
_PENDING_ORDER_TYPES = frozenset({
    OrderType.LIMIT,
    OrderType.STOP,
    OrderType.STOP_LIMIT,
})
_PENDING_ORDER_TYPE_NAMES = frozenset({"limit", "stop", "stop_limit"})


def resolve_expiration_minutes(
    ai_minutes: int | None,
    default_minutes: int,
) -> int | None:
    if ai_minutes is not None:
        return ai_minutes if ai_minutes > 0 else None
    if default_minutes <= 0:
        return None
    return default_minutes


def build_expiration_options(minutes: int) -> dict:
    return {
        "type": _EXPIRATION_TYPE,
        "minutes": minutes,
        "time": datetime.now(UTC) + timedelta(minutes=minutes),
    }


def apply_pending_order_expiration(
    options: dict,
    order_type: OrderType | str,
    ai_expiration_minutes: int | None,
    default_expiration_minutes: int,
) -> dict:
    if isinstance(order_type, str):
        if order_type.lower() not in _PENDING_ORDER_TYPE_NAMES:
            return options
    elif order_type not in _PENDING_ORDER_TYPES:
        return options

    minutes = resolve_expiration_minutes(
        ai_expiration_minutes,
        default_expiration_minutes,
    )
    if minutes is None:
        return options

    return {**options, "expiration": build_expiration_options(minutes)}
