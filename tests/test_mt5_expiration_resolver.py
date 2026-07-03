import unittest
from unittest.mock import MagicMock, patch

import MetaTrader5 as mt5

from trading.mt5.expiration_resolver import (
    _SYMBOL_EXPIRATION_DAY,
    _SYMBOL_EXPIRATION_GTC,
    _SYMBOL_EXPIRATION_SPECIFIED,
    apply_mt5_pending_expiration,
)


class MT5ExpirationResolverTests(unittest.TestCase):
    def test_specified_uses_server_time_plus_minutes(self):
        request: dict = {"symbol": "GOLDmicro", "type_time": mt5.ORDER_TIME_GTC}
        info = MagicMock(expiration_mode=_SYMBOL_EXPIRATION_SPECIFIED)
        tick = MagicMock(time=1_700_000_000)

        with patch("trading.mt5.expiration_resolver.mt5.symbol_info", return_value=info), patch(
            "trading.mt5.expiration_resolver.mt5.symbol_info_tick",
            return_value=tick,
        ):
            apply_mt5_pending_expiration(request, "GOLDmicro", 25)

        self.assertEqual(request["type_time"], mt5.ORDER_TIME_SPECIFIED)
        self.assertEqual(request["expiration"], 1_700_000_000 + 25 * 60)

    def test_specified_floors_short_expiration_to_minimum(self):
        request: dict = {"symbol": "GOLDmicro", "type_time": mt5.ORDER_TIME_GTC}
        info = MagicMock(expiration_mode=_SYMBOL_EXPIRATION_SPECIFIED)
        tick = MagicMock(time=1_700_000_000)

        with patch("trading.mt5.expiration_resolver.mt5.symbol_info", return_value=info), patch(
            "trading.mt5.expiration_resolver.mt5.symbol_info_tick",
            return_value=tick,
        ), patch("trading.mt5.expiration_resolver.logger") as log:
            apply_mt5_pending_expiration(request, "GOLDmicro", 1)

        self.assertEqual(request["expiration"], 1_700_000_000 + 120)
        log.warning.assert_called_once()

    def test_gtc_only_symbol_skips_expiration(self):
        request: dict = {"symbol": "GOLDmicro", "type_time": mt5.ORDER_TIME_GTC}
        info = MagicMock(expiration_mode=_SYMBOL_EXPIRATION_GTC)
        tick = MagicMock(time=1_700_000_000)

        with patch("trading.mt5.expiration_resolver.mt5.symbol_info", return_value=info), patch(
            "trading.mt5.expiration_resolver.mt5.symbol_info_tick",
            return_value=tick,
        ):
            apply_mt5_pending_expiration(request, "GOLDmicro", 25)

        self.assertEqual(request["type_time"], mt5.ORDER_TIME_GTC)
        self.assertNotIn("expiration", request)

    def test_gtc_mode_does_not_warn_about_short_expiration(self):
        request: dict = {"symbol": "GOLDmicro", "type_time": mt5.ORDER_TIME_GTC}
        info = MagicMock(expiration_mode=_SYMBOL_EXPIRATION_GTC)
        tick = MagicMock(time=1_700_000_000)

        with patch("trading.mt5.expiration_resolver.mt5.symbol_info", return_value=info), patch(
            "trading.mt5.expiration_resolver.mt5.symbol_info_tick",
            return_value=tick,
        ), patch("trading.mt5.expiration_resolver.logger") as log:
            apply_mt5_pending_expiration(request, "GOLDmicro", 1)

        self.assertEqual(request["type_time"], mt5.ORDER_TIME_GTC)
        log.warning.assert_not_called()

    def test_day_mode_uses_order_time_day(self):
        request: dict = {"symbol": "GOLDmicro", "type_time": mt5.ORDER_TIME_GTC}
        info = MagicMock(
            expiration_mode=_SYMBOL_EXPIRATION_DAY | _SYMBOL_EXPIRATION_GTC,
        )
        tick = MagicMock(time=1_700_000_000)

        with patch("trading.mt5.expiration_resolver.mt5.symbol_info", return_value=info), patch(
            "trading.mt5.expiration_resolver.mt5.symbol_info_tick",
            return_value=tick,
        ):
            apply_mt5_pending_expiration(request, "GOLDmicro", 25)

        self.assertEqual(request["type_time"], mt5.ORDER_TIME_DAY)
        self.assertNotIn("expiration", request)


if __name__ == "__main__":
    unittest.main()
