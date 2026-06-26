from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.group_magic import group_magic_map, magic_from_group_id
from config.order_limits import (
    AGGRESSIVE_ORDERS_PER_MESSAGE,
    NORMAL_ORDERS_PER_MESSAGE,
)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_name: str = "tgtrading"
    telegram_group_ids: str = Field(
        description="Comma-separated Telegram group chat IDs",
    )

    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    gemini_fallback_models: str = Field(
        default="gemini-2.0-flash,gemini-2.5-flash-lite",
    )

    metaapi_token: str
    metaapi_account_id: str

    default_volume: float = 0.01
    min_volume: float = Field(default=0.01, gt=0)
    max_volume: float = Field(default=1.0, gt=0)
    trading_enabled: bool = False
    allowed_symbols: str = Field(default="EURUSD,XAUUSD,GBPUSD")
    default_symbol: str | None = None

    max_order_count: int = Field(default=20, ge=1)
    max_order_per_group: int = Field(default=5, ge=1)
    context_message_count: int = Field(default=5, ge=1)
    aggressive_mode: bool = False
    orders_expiration_minutes: int = Field(
        default=20,
        ge=0,
        alias="ORDERS_EXPIRATION",
        description="Default pending order expiration in minutes when AI returns null",
    )
    default_sl_pips: float = Field(
        default=300.0,
        gt=0,
        validation_alias=AliasChoices("default_SL", "DEFAULT_SL"),
    )
    default_tp_pips: float = Field(
        default=500.0,
        gt=0,
        validation_alias=AliasChoices("default_TP", "DEFAULT_TP"),
    )

    @property
    def max_orders_per_message(self) -> int:
        if self.aggressive_mode:
            return AGGRESSIVE_ORDERS_PER_MESSAGE
        return NORMAL_ORDERS_PER_MESSAGE

    @property
    def effective_max_per_message(self) -> int:
        """Rejim (2/5) va env MAX_ORDER_PER_GROUP dan qattiqroq limit."""
        return min(self.max_orders_per_message, self.max_order_per_group)

    @property
    def group_magic_list(self) -> list[int]:
        return list(self.group_magic_by_id.values())

    @property
    def group_magic_by_id(self) -> dict[int, int]:
        return group_magic_map(self.parsed_group_ids)

    def get_group_magic(self, chat_id: int) -> int:
        if chat_id not in self.parsed_group_ids:
            raise ValueError(f"Group {chat_id} not in TELEGRAM_GROUP_IDS")
        return magic_from_group_id(chat_id)

    @property
    def parsed_group_ids(self) -> list[int]:
        return [
            int(chat_id.strip())
            for chat_id in self.telegram_group_ids.split(",")
            if chat_id.strip()
        ]

    @property
    def parsed_allowed_symbols(self) -> list[str]:
        return [s.strip() for s in self.allowed_symbols.split(",") if s.strip()]

    @property
    def parsed_fallback_models(self) -> list[str]:
        return [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
