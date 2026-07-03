import unittest

from ai.close_all_detector import message_asks_close_all
from ai.close_all_patcher import apply_close_all_from_message
from ai.duplicate_zone_guard import remove_duplicate_zone_entries
from ai.noise_message_filter import is_reaction_noise, suppress_noise_entries
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder


class CloseAllDetectorTests(unittest.TestCase):
    def test_yoping(self):
        self.assertTrue(message_asks_close_all("YOPING"))
        self.assertTrue(message_asks_close_all("close all trades"))
        self.assertTrue(message_asks_close_all("YOPING 🔥"))
        self.assertTrue(message_asks_close_all("hammasini yop"))
        self.assertTrue(message_asks_close_all("signal cancel"))

    def test_not_close_all(self):
        self.assertFalse(message_asks_close_all("Hit TP1 secure half"))
        self.assertFalse(message_asks_close_all("Gold sell now"))
        self.assertFalse(message_asks_close_all("50% close then BE"))


class CloseAllPatcherTests(unittest.TestCase):
    def test_closes_all_group_orders(self):
        existing = [
            ExistingOrder(
                order_number="1",
                open_price=4070.0,
                volume=0.02,
                side="sell",
                order_type="market",
                symbol="XAUUSDm",
                is_position=True,
            ),
            ExistingOrder(
                order_number="2",
                open_price=4075.0,
                volume=0.01,
                side="sell",
                order_type="limit",
                symbol="XAUUSDm",
                is_position=False,
            ),
        ]
        response = AiTradeResponse(
            is_signal=False,
            reasoning="LLM missed close",
        )
        patched = apply_close_all_from_message(response, existing, "YOPING")

        self.assertTrue(patched.is_signal)
        self.assertEqual(len(patched.orders), 2)
        self.assertEqual({o.count_order for o in patched.orders}, {1, 2})
        self.assertTrue(all(o.action_type == "close" for o in patched.orders))


class DuplicateZoneGuardTests(unittest.TestCase):
    def test_skips_existing_pending_price(self):
        existing = [
            ExistingOrder(
                order_number="10",
                open_price=4075.0,
                volume=0.01,
                side="sell",
                order_type="limit",
                symbol="XAUUSDm",
                is_position=False,
            ),
        ]
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            orders=[
                AiOrderAction(
                    count_order=1,
                    action_type="entry",
                    price=4075.0,
                    order_type="limit",
                ),
                AiOrderAction(
                    count_order=1,
                    action_type="entry",
                    price=4080.0,
                    order_type="limit",
                ),
            ],
        )
        result = remove_duplicate_zone_entries(response, existing)
        prices = [o.price for o in result.orders if o.action_type == "entry"]
        self.assertEqual(prices, [4080.0])


class NoiseFilterTests(unittest.TestCase):
    def test_emoji_only_is_noise(self):
        self.assertTrue(is_reaction_noise("😡🔥"))
        self.assertTrue(is_reaction_noise("BUM 😡"))

    def test_sell_not_noise(self):
        self.assertFalse(is_reaction_noise("Gold sell now"))

    def test_suppresses_spam_entries(self):
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            orders=[
                AiOrderAction(count_order=1, action_type="entry", order_type="market"),
            ],
        )
        existing = [
            ExistingOrder(
                order_number="1",
                open_price=4070.0,
                volume=0.02,
                side="sell",
                order_type="market",
                symbol="XAUUSDm",
                is_position=True,
            ),
        ]
        result = suppress_noise_entries(response, existing, "BUM 😡")
        self.assertFalse(result.is_signal)


if __name__ == "__main__":
    unittest.main()
