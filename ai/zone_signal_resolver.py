from models.signal import SignalAnalysis


def resolve_zone_fields(signal: SignalAnalysis) -> SignalAnalysis:
    if signal.entry_zone_low is not None and signal.entry_zone_high is not None:
        return signal

    if len(signal.entry_levels) < 2:
        return signal

    prices = [level.price for level in signal.entry_levels]
    signal.entry_zone_low = min(prices)
    signal.entry_zone_high = max(prices)
    return signal
