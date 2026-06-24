from pydantic import BaseModel


class ExistingOrder(BaseModel):
    order_number: str
    open_time: str | None = None
    open_price: float
    volume: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    side: str
    order_type: str
    symbol: str
    is_position: bool = False
