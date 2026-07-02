from typing import Any

from config.settings import Settings


def create_trading_service(settings: Settings, *, win_mode: bool) -> Any:
    if win_mode:
        from trading.mt5.service import MT5Service
        return MT5Service(settings)

    from trading.metaapi.service import MetaApiService
    return MetaApiService(settings)


def create_connection_keeper(
    trading: Any,
    *,
    win_mode: bool,
    settings: Settings | None = None,
) -> Any:
    if win_mode:
        from trading.mt5.connection_keeper import MT5ConnectionKeeper
        return MT5ConnectionKeeper(trading)

    from trading.metaapi.connection_keeper import MetaApiConnectionKeeper
    keeper = MetaApiConnectionKeeper(trading)
    trading.attach_keeper(keeper)
    return keeper
