from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.group_magic import group_magic_map, magic_from_group_id
from config.order_limits import NORMAL_ORDERS_PER_MESSAGE

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

    metaapi_token: str | None = Field(default=None, description="MetaAPI cloud token")
    metaapi_account_id: str | None = Field(
        default=None,
        description="MetaAPI MT account UUID",
    )

    mt5_path: str | None = Field(default=None, description="MT5 terminal64.exe path")
    mt5_login: int | None = Field(default=None, description="MT5 account login")

    @field_validator("mt5_login", mode="before")
    @classmethod
    def empty_login_to_none(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value

    @field_validator("metaapi_token", "metaapi_account_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("mt5_path", mode="before")
    @classmethod
    def normalize_mt5_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = str(value).strip().strip('"').strip("'")
        if not path:
            return None
        # .env da \terminal64 kabi yozuv \t (tab) ga aylanadi
        tab = "\t"
        path = path.replace(f"{tab}erminal64", "\\terminal64")
        path = path.replace(f"{tab}erminal64.exe", "\\terminal64.exe")
        return path.replace("/", "\\")
    mt5_password: str | None = Field(default=None, description="MT5 account password")
    mt5_server: str | None = Field(default=None, description="Broker server name")
    mt5_timeout: int = Field(default=60000, ge=1000, description="Initialize timeout ms")

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
        default=5000,
        ge=0,
        validation_alias=AliasChoices(
            "default_SL",
            "DEFAULT_SL",
            "DEFAULT_SL_PIPS",
        ),
        description="Signalda SL yo'q bo'lsa entry dan pip masofasi (0=o'chirilgan)",
    )
    default_tp_pips: float = Field(
        default=10000,
        ge=0,
        validation_alias=AliasChoices(
            "default_TP",
            "DEFAULT_TP",
            "DEFAULT_TP_PIPS",
        ),
        description="Signalda TP yo'q bo'lsa entry dan pip masofasi (0=o'chirilgan)",
    )
    auto_be_pips: float = Field(
        default=100,
        ge=0,
        alias="AUTO_BE_PIPS",
        description="Har xabar kelganda profit shu pip dan oshsa SL=openPrice (0=o'chirilgan)",
    )
    log_dir: str = Field(default="logs", alias="LOG_DIR")
    log_retention_days: int = Field(
        default=30,
        ge=1,
        alias="LOG_RETENTION_DAYS",
        description="Kunlik log fayllarini necha kun saqlash",
    )
    log_to_file: bool = Field(default=True, alias="LOG_TO_FILE")
    log_to_console: bool = Field(default=True, alias="LOG_TO_CONSOLE")

    @property
    def max_orders_per_message(self) -> int:
        if self.aggressive_mode:
            return self.max_order_per_group
        return min(NORMAL_ORDERS_PER_MESSAGE, self.max_order_per_group)

    @property
    def effective_max_per_message(self) -> int:
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
