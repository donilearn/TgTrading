from dataclasses import dataclass


@dataclass
class SpotQuote:
    bid: float | None
    ask: float | None


class SpotCache:
    """ProtoOASpotEvent dan kelgan narxlar."""

    def __init__(self) -> None:
        self._quotes: dict[int, SpotQuote] = {}

    def update(self, symbol_id: int, bid: int | None, ask: int | None) -> None:
        self._quotes[symbol_id] = SpotQuote(
            bid=_price_from_proto(bid),
            ask=_price_from_proto(ask),
        )

    def get(self, symbol_id: int) -> SpotQuote | None:
        return self._quotes.get(symbol_id)


def _price_from_proto(value: int | None) -> float | None:
    if value is None:
        return None
    return value / 100_000.0
