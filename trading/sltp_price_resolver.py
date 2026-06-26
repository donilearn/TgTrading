from typing import Any

from trading.price_normalizer import normalize_price


def pip_size_from_spec(spec: dict) -> float | None:
    tick = _float(spec.get("tickSize"))
    if not tick or tick <= 0:
        return None

    digits = _int(spec.get("digits"))
    if digits in (3, 5):
        return tick * 10
    return tick


def resolve_default_sltp_prices(
    *,
    side: str,
    entry_price: float | None,
    spec: dict,
    default_sl_pips: float,
    default_tp_pips: float,
    existing_sl: float | None = None,
    existing_tp: float | None = None,
) -> tuple[float | None, float | None]:
    """Signalda SL/TP yo'q bo'lsa default pip masofasidan narx hisoblaydi."""
    if entry_price is None:
        return existing_sl, existing_tp

    pip_size = pip_size_from_spec(spec)
    if pip_size is None:
        return existing_sl, existing_tp

    is_buy = side.lower() == "buy"
    sl = existing_sl
    tp = existing_tp

    if sl is None and default_sl_pips > 0:
        distance = default_sl_pips * pip_size
        raw_sl = entry_price - distance if is_buy else entry_price + distance
        sl = normalize_price(raw_sl, spec)

    if tp is None and default_tp_pips > 0:
        distance = default_tp_pips * pip_size
        raw_tp = entry_price + distance if is_buy else entry_price - distance
        tp = normalize_price(raw_tp, spec)

    return sl, tp


def market_entry_price(side: str, price: dict[str, Any]) -> float | None:
    is_buy = side.lower() == "buy"
    key = "ask" if is_buy else "bid"
    return _float(price.get(key))


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
