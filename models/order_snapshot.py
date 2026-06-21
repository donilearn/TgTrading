from pydantic import BaseModel


class OrderSnapshot(BaseModel):
    id: str
    symbol: str
    order_type: str
    volume: float
    open_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    magic: int | None = None
