from models.existing_order import ExistingOrder
from trading.volume_normalizer import round_volume


def resolve_close_volume(
    requested_volume: float | None,
    position: ExistingOrder,
    min_volume: float,
) -> tuple[str, float | None]:
    """To'liq yoki qisman yopish hajmini aniqlaydi."""
    if requested_volume is None or requested_volume <= 0:
        return "full", None

    position_volume = position.volume
    if position_volume is None or position_volume <= 0:
        return "full", None

    close_volume = round_volume(requested_volume)
    if close_volume >= position_volume - 1e-9:
        return "full", None

    if close_volume < min_volume:
        return "too_small", None

    return "partial", close_volume
