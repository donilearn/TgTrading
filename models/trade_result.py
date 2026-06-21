from pydantic import BaseModel, Field


class TradeResult(BaseModel):
    success: bool
    string_code: str = ""
    numeric_code: int | None = None
    symbol: str = ""
    action: str = ""
    volume: float = 0.0
    message: str = ""
    skipped: bool = Field(
        default=False,
        description="Trade was skipped (dry-run or invalid signal)",
    )
