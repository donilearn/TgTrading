def resolve_short_price(value: float, reference: float | None) -> float:
    """Qisqa narxni (masalan 105) joriy narx kontekstida to'liq narxga aylantiradi."""
    if reference is None or reference <= 0:
        return value

    if value >= reference * 0.5:
        return value

    ref_int = int(reference)
    short_int = int(value)
    short_digits = len(str(abs(short_int)))
    if short_digits <= 0:
        return value

    divisor = 10 ** short_digits
    prefix = (ref_int // divisor) * divisor
    return float(prefix + short_int)
