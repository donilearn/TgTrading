from typing import Any

from models.symbol_market_info import SymbolMarketInfo
from trading.metaapi_trading_snapshot import MetaApiTradingSnapshot


class MetaApiTerminalReader:
    """Streaming terminal_state dan o'qish — RPC chaqiruvsiz, yuk kam."""

    def read_snapshot(self, terminal_state: Any) -> MetaApiTradingSnapshot:
        positions = terminal_state.positions or []
        orders = terminal_state.orders or []
        return MetaApiTradingSnapshot(
            positions=[_as_dict(item) for item in positions],
            orders=[_as_dict(item) for item in orders],
        )

    def read_market(
        self,
        terminal_state: Any,
        symbols: set[str],
    ) -> list[SymbolMarketInfo]:
        market: list[SymbolMarketInfo] = []
        for symbol in sorted(symbols):
            spec = terminal_state.specification(symbol)
            quote = terminal_state.price(symbol)
            if spec is None or quote is None:
                continue
            spec_dict = _as_dict(spec)
            quote_dict = _as_dict(quote)
            market.append(SymbolMarketInfo(
                symbol=symbol,
                bid=_float(quote_dict.get("bid")),
                ask=_float(quote_dict.get("ask")),
                digits=_int(spec_dict.get("digits")),
                tick_size=_float(spec_dict.get("tickSize")),
                volume_step=_float(spec_dict.get("volumeStep")),
                min_volume=_float(spec_dict.get("minVolume")),
            ))
        return market


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return dict(value)


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
