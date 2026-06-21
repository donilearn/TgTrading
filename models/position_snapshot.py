from pydantic import BaseModel


class PositionSnapshot(BaseModel):
    id: str
    symbol: str
    side: str
    volume: float
    open_price: float
    current_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    profit: float | None = None
    magic: int | None = None
