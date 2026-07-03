import unittest
from unittest.mock import MagicMock

from ai.close_all_detector import message_asks_close_all
from ai.management_message_detector import message_needs_broker_context
from ai.partial_close_patcher import (
    apply_partial_close_from_message,
    message_asks_partial_close,
)
from ai.type1_zone_entry_sync import sync_type1_zone_entries
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder


class ManagementDetectorTests(unittest.TestCase):
    def test_pips_update_needs_context(self):
        text = "GOLD SELL 160 PIPS ++ ✅\nHit TP1 guys make sure secure half"
        self.assertTrue(message_needs_broker_context(text))

    def test_plain_sell_now_does_not(self):
        self.assertFalse(message_needs_broker_context("Gold sell now"))

    def test_zone_signal_does_not(self):
        text = "Gold sell @4075 - 4080\nSl : 4085\ntp1 : 4065\ntp2 : 4055"
        self.assertFalse(message_needs_broker_context(text))

    def test_yoping_needs_broker_context(self):
        self.assertTrue(message_needs_broker_context("YOPING"))
        self.assertTrue(message_needs_broker_context("close all ✅"))
        self.assertTrue(message_needs_broker_context("signal cancel invalid"))

    def test_partial_close_not_close_all(self):
        self.assertFalse(message_asks_close_all("50% close half then BE"))


class PartialClosePatcherTests(unittest.TestCase):
    def test_secure_half_adds_close(self):
        settings = Settings(auto_be_pips=150, min_volume=0.01)
        existing = [
            ExistingOrder(
                order_number="123",
                open_price=4073.0,
                volume=0.02,
                side="sell",
                order_type="market",
                symbol="XAUUSDm",
                is_position=True,
            ),
        ]
        response = AiTradeResponse(
            is_signal=False,
            symbol="XAUUSDm",
            side="none",
            reasoning="no positions in LLM context",
        )
        text = "Hit TP1 guys make sure secure half then set BE okay."

        self.assertTrue(message_asks_partial_close(text))
        patched = apply_partial_close_from_message(
            response, existing, text, settings,
        )

        self.assertTrue(patched.is_signal)
        self.assertEqual(len(patched.orders), 1)
        self.assertEqual(patched.orders[0].action_type, "close")
        self.assertEqual(patched.orders[0].volume, 0.01)


class Type1ZoneSyncTests(unittest.TestCase):
    def test_existing_market_opens_all_zone_limits(self):
        settings = MagicMock()
        settings.default_volume = 0.01
        settings.min_volume = 0.01
        settings.max_volume = 0.1
        settings.orders_expiration_minutes = 30

        existing = [
            ExistingOrder(
                order_number="1903691083",
                open_price=4073.635,
                volume=0.02,
                side="sell",
                order_type="market",
                symbol="XAUUSDm",
                is_position=True,
            ),
        ]
        message = (
            "Gold sell @4075 - 4080\n\nSl : 4085\n\ntp1 : 4065\ntp2 : 4055"
        )
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            zone_low=4075.0,
            zone_high=4080.0,
            orders=[
                AiOrderAction(
                    count_order=1,
                    action_type="entry",
                    price=4075.0,
                    sl=4085.0,
                    tp=4065.0,
                    order_type="limit",
                    volume=0.01,
                ),
                AiOrderAction(
                    count_order=2,
                    action_type="entry",
                    price=4080.0,
                    sl=4085.0,
                    tp=4055.0,
                    order_type="limit",
                    volume=0.01,
                ),
            ],
        )

        result = sync_type1_zone_entries(
            response, existing, message, settings, market=None,
        )

        limits = [
            o for o in result.orders
            if o.action_type == "entry" and o.order_type == "limit"
        ]
        prices = sorted(o.price for o in limits if o.price is not None)
        self.assertEqual(prices, [4075.0, 4080.0])

        modifies = [o for o in result.orders if o.action_type == "modify"]
        self.assertEqual(len(modifies), 1)
        self.assertEqual(modifies[0].count_order, 1903691083)


if __name__ == "__main__":
    unittest.main()
