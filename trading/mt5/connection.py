import logging
from typing import Any

import MetaTrader5 as mt5

from config.settings import Settings
from trading.mt5.filling_resolver import resolve_filling_mode
from trading.mt5.snapshot_mapper import SnapshotMapper
from trading.mt5.symbol_helper import normalize_volume
from trading.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)

_SUCCESS_RETCODES = frozenset({
    mt5.TRADE_RETCODE_DONE,
    mt5.TRADE_RETCODE_PLACED,
    mt5.TRADE_RETCODE_NO_CHANGES,
})
_CHECK_OK = frozenset({0, mt5.TRADE_RETCODE_DONE})


class MT5Connection:
    """Sinxron MT5 terminal ulanishi."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connected = False

    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        info = mt5.terminal_info()
        alive = info is not None and info.connected
        if not alive:
            self._connected = False
        return alive

    def connect(self) -> None:
        init_kwargs: dict[str, Any] = {
            "timeout": self._settings.mt5_timeout,
        }
        if self._settings.mt5_path:
            init_kwargs["path"] = self._settings.mt5_path

        if not mt5.initialize(**init_kwargs):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

        login_kwargs: dict[str, Any] = {
            "login": self._settings.mt5_login,
            "password": self._settings.mt5_password,
        }
        if self._settings.mt5_server:
            login_kwargs["server"] = self._settings.mt5_server

        if not mt5.login(**login_kwargs):
            mt5.shutdown()
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")

        self._connected = True
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        logger.info(
            "MT5 connected login=%s server=%s terminal=%s",
            self._settings.mt5_login,
            account.server if account else "?",
            terminal.name if terminal else "?",
        )
        self._log_trading_readiness(terminal, account)

    def _log_trading_readiness(self, terminal, account) -> None:
        if terminal is not None and not terminal.trade_allowed:
            logger.warning(
                "MT5: terminal trade_allowed=False — savdo cheklangan bo'lishi mumkin"
            )
        if account is not None and not account.trade_allowed:
            logger.warning(
                "MT5: account trade_allowed=False — hisobda savdo o'chirilgan"
            )
        logger.info(
            "MT5: 'Algo Trading' tugmasi yoqilgan bo'lishi shart "
            "(toolbar → AutoTrading / Algo Trading)"
        )

    def disconnect(self) -> None:
        if self._connected:
            mt5.shutdown()
        self._connected = False
        logger.info("MT5 disconnected")

    def reconnect(self) -> None:
        self.disconnect()
        self.connect()

    def fetch_snapshot(self) -> TradingSnapshot:
        positions = mt5.positions_get() or []
        orders = mt5.orders_get() or []
        return SnapshotMapper.from_mt5(positions, orders)

    def send_request(self, request: dict) -> dict:
        symbol = request.get("symbol")
        if symbol and "volume" in request:
            request = {
                **request,
                "volume": normalize_volume(symbol, float(request["volume"])),
            }

        if request.get("action") == mt5.TRADE_ACTION_DEAL and "type_filling" not in request:
            request = {
                **request,
                "type_filling": resolve_filling_mode(symbol, request),
            }

        check = mt5.order_check(request)
        if check is not None and check.retcode not in _CHECK_OK:
            raise RuntimeError(_format_trade_error(check.retcode, check.comment))

        result = mt5.order_send(request)
        if result is None:
            error = mt5.last_error()
            raise RuntimeError(f"MT5 order_send failed: {error}")

        if result.retcode not in _SUCCESS_RETCODES:
            raise RuntimeError(_format_trade_error(result.retcode, result.comment))

        return {
            "stringCode": "TRADE_RETCODE_DONE",
            "retcode": result.retcode,
            "order": result.order,
            "deal": result.deal,
            "comment": result.comment,
        }


def _format_trade_error(retcode: int, comment: str) -> str:
    if retcode == mt5.TRADE_RETCODE_CLIENT_DISABLES_AT:
        return (
            "MT5 Algo Trading o'chirilgan — terminalda "
            "'Algo Trading' / 'AutoTrading' tugmasini yoqing"
        )
    return f"MT5 order failed retcode={retcode} comment={comment}"
