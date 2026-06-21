def evenly_spaced_prices(zone_low: float, zone_high: float, count: int) -> list[float]:
    low = min(zone_low, zone_high)
    high = max(zone_low, zone_high)

    if count <= 1:
        return [_round_price((low + high) / 2, low, high)]

    step = (high - low) / (count - 1)
    return [
        _round_price(low + step * index, low, high)
        for index in range(count)
    ]


def _round_price(value: float, low: float, high: float) -> float:
    span = abs(high - low)
    if span >= 1000 or max(abs(low), abs(high)) >= 10000:
        return round(value)
    if span >= 1:
        return round(value, 2)
    return round(value, 5)
