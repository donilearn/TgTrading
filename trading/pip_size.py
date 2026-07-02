"""Broker digits/tick bo'yicha bitta pip narx masofasi."""

from typing import Any


def pip_size_from_spec(spec: dict) -> float | None:
    """
    1 pip = necha price unit.

    Ustuvor: broker `pipSize` (MetaAPI/MT5).
    Keyin digits + tickSize (point):
      - digits 3 yoki 5 → 1 pip = 10 * tick  (masalan XAU 2650.123, EUR 1.12345)
      - digits 2 yoki 4 → 1 pip = 1 * tick   (masalan XAU 2650.12, EUR 1.1234)
    """
    broker_pip = _float(spec.get("pipSize"))
    if broker_pip is not None and broker_pip > 0:
        return broker_pip

    tick = _float(spec.get("tickSize")) or _float(spec.get("point"))
    if tick is None or tick <= 0:
        return None

    digits = _int(spec.get("digits"))
    if digits in (3, 5):
        return tick * 10
    return tick


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
