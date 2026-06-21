from pydantic import BaseModel


class SymbolQuote(BaseModel):
    symbol: str
    bid: float | None = None
    ask: float | None = None
    time: str | None = None
    pip_size: float | None = None
    digits: int | None = None
