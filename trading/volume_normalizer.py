import math


def split_volume(
    total_volume: float,
    max_orders: int,
    min_volume: float,
    max_volume: float,
) -> tuple[list[float], int]:
    if max_orders < 1:
        max_orders = 1

    count = max_orders
    while count > 1 and total_volume / count < min_volume - 1e-9:
        count -= 1

    per_order = total_volume / count
    if per_order > max_volume:
        count = max(1, math.ceil(total_volume / max_volume))
        per_order = total_volume / count

    volumes = [_round_volume(min(max(per_order, min_volume), max_volume)) for _ in range(count)]

    allocated = sum(volumes)
    if allocated > total_volume + 1e-9:
        volumes[-1] = _round_volume(max(min_volume, volumes[-1] - (allocated - total_volume)))

    return volumes, count


def split_volume_for_zone(
    total_volume: float,
    max_orders: int,
    min_volume: float,
    max_volume: float,
) -> tuple[list[float], int]:
    """Zone grid: always max_orders slots, each at least min_volume."""
    count = max(1, max_orders)
    per_order = total_volume / count

    if per_order < min_volume:
        per_order = min_volume

    per_order = min(per_order, max_volume)
    volumes = [_round_volume(per_order) for _ in range(count)]
    return volumes, count


def round_volume(value: float) -> float:
    return round(value, 2)


def _round_volume(value: float) -> float:
    return round_volume(value)
