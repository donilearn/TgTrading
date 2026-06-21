from pydantic import BaseModel, Field


class TakeProfitLevel(BaseModel):
    level: int = Field(default=1, ge=1, description="TP level number e.g. TP1=1, TP2=2")
    price: float = Field(description="Take profit price")
    volume_percent: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Percent of total volume to close at this TP",
    )
