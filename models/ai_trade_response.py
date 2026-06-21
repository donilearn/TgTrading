from pydantic import BaseModel, Field

from models.ai_order_action import AiOrderAction


class AiTradeResponse(BaseModel):
    is_signal: bool = Field(description="Xabar trade signalmi")
    symbol: str | None = Field(default=None, description="Aniq broker symbol nomi")
    side: str = Field(default="none", description="buy | sell | none")
    orders: list[AiOrderAction] = Field(default_factory=list)
    reasoning: str = Field(default="")

    @property
    def is_actionable(self) -> bool:
        return self.is_signal and bool(self.symbol) and len(self.orders) > 0
