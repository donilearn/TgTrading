from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.pip_size import pip_size_from_spec


def position_profit_pips(
    position: ExistingOrder,
    market: SymbolMarketInfo | None,
    spec: dict,
) -> float | None:
    """Ochiq pozitsiya floating profitini pip da qaytaradi."""
    pip_size = pip_size_from_spec(spec)
    if pip_size is None or pip_size <= 0:
        return None
    if market is None:
        return None

    side = position.side.lower()
    if side == "buy":
        current = market.bid
        if current is None:
            return None
        return (current - position.open_price) / pip_size

    if side == "sell":
        current = market.ask
        if current is None:
            return None
        return (position.open_price - current) / pip_size

    return None
