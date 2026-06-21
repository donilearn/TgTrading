from pydantic import BaseModel


class SymbolMarketInfo(BaseModel):
    symbol: str
    bid: float | None = None
    ask: float | None = None
    digits: int | None = None
    tick_size: float | None = None
    volume_step: float | None = None
    min_volume: float | None = None
