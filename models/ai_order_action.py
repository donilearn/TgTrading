from pydantic import BaseModel, ConfigDict, Field


class AiOrderAction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    count_order: int = Field(
        alias="countOrder",
        description="entry: nechta order ochish. modify/close/cancel: mavjud order number",
    )
    action_type: str = Field(
        alias="type",
        description="entry | modify | close | cancel",
    )
    price: float | None = Field(
        default=None,
        description="Entry yoki modify uchun narx",
    )
    sl: float | None = Field(
        default=None,
        description="Stop loss narx. Faqat joriy signalda SL aytilganda. Yo'q bo'lsa null.",
    )
    tp: float | None = Field(
        default=None,
        description="Take profit narx. Faqat joriy signalda TP aytilganda. Yo'q bo'lsa null.",
    )
    order_type: str = Field(
        default="limit",
        alias="orderType",
        description="limit | stop | market",
    )
    volume: float | None = Field(
        default=None,
        description="Lot hajmi (bo'sh bo'lsa default ishlatiladi)",
    )
    expiration_minutes: int | None = Field(
        default=None,
        alias="expirationMinutes",
        description=(
            "Pending order expire (minut). null=ORDERS_EXPIRATION default. "
            "0=expire yo'q (GTC). limit/stop uchun."
        ),
    )
