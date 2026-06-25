def build_stop_options(
    price: float | None,
    pips: float | None,
) -> float | None:
    if pips is not None:
        return pips
    return price
