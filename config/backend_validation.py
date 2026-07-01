import sys

from config.settings import Settings


def validate_backend_settings(settings: Settings, *, win_mode: bool) -> None:
    """Backend bo'yicha majburiy .env maydonlarini tekshiradi."""
    if win_mode:
        if sys.platform != "win32":
            raise SystemExit("--win requires Windows (local MetaTrader5 API)")
        if settings.mt5_login is None or not settings.mt5_password:
            raise SystemExit("MT5_LOGIN and MT5_PASSWORD are required for --win mode")
        return

    if not settings.metaapi_token or not settings.metaapi_account_id:
        raise SystemExit(
            "METAAPI_TOKEN and METAAPI_ACCOUNT_ID are required "
            "(default MetaAPI mode). Use --win for local MT5.",
        )


def backend_label(win_mode: bool) -> str:
    return "MT5 (local)" if win_mode else "MetaAPI (cloud)"
