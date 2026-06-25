"""cTrader protokol ↔ lot/narx konvertatsiyasi."""


def lots_to_volume(lots: float) -> int:
    """0.01 lot = 1 protokol volume."""
    return int(round(lots * 100))


def volume_to_lots(volume: int) -> float:
    return volume / 100.0


def tick_size_from_digits(digits: int) -> float:
    if digits <= 0:
        return 0.00001
    return 10 ** (-digits)
