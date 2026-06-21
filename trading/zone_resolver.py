from models.signal import SignalAnalysis


def resolve_zone(signal: SignalAnalysis) -> tuple[float, float] | None:
    if signal.entry_zone_low is not None and signal.entry_zone_high is not None:
        low = min(signal.entry_zone_low, signal.entry_zone_high)
        high = max(signal.entry_zone_low, signal.entry_zone_high)
        if low != high:
            return low, high
        return None

    if len(signal.entry_levels) >= 2:
        prices = [level.price for level in signal.entry_levels]
        return min(prices), max(prices)

    return None
