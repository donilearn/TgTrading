from pydantic import BaseModel, Field

from models.order_snapshot import OrderSnapshot
from models.position_snapshot import PositionSnapshot
from models.symbol_quote import SymbolQuote


class TradingSnapshot(BaseModel):
    magic: int
    positions: list[PositionSnapshot] = Field(default_factory=list)
    orders: list[OrderSnapshot] = Field(default_factory=list)
    quotes: list[SymbolQuote] = Field(default_factory=list)
