from pydantic import BaseModel, Field


class EntryLevel(BaseModel):
    level: int = Field(default=1, ge=1, description="Entry level number e.g. 1, 2")
    price: float = Field(description="Entry price for limit/stop orders")
    volume: float | None = Field(
        default=None,
        description="Lot size for this entry; if null, volume is split equally",
    )
