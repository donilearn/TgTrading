import logging
from typing import Any

import MetaTrader5 as mt5

from config.settings import Settings
from trading.mt5.snapshot_mapper import SnapshotMapper
from trading.trading_snapshot import TradingSnapshot

logger = logging.getLogger(__name__)


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
        return info is not None and info.connected

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
        result = mt5.order_send(request)
        if result is None:
            error = mt5.last_error()
            raise RuntimeError(f"MT5 order_send failed: {error}")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(
                f"MT5 order failed retcode={result.retcode} "
                f"comment={result.comment}"
            )

        return {
            "stringCode": "TRADE_RETCODE_DONE",
            "retcode": result.retcode,
            "order": result.order,
            "deal": result.deal,
            "comment": result.comment,
        }
