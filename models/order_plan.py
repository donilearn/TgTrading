from pydantic import BaseModel, Field

from models.order_type import OrderType


class OrderPlan(BaseModel):
    volume: float
    entry_price: float | None = None
    order_type: OrderType | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    sl_pips: float | None = None
    tp_pips: float | None = None
